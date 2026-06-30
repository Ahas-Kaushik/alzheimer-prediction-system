from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from backend.agents import agent2_pet_synthesizer
from backend.api.schemas.scan_schema import ScanStatusOut, ScanUploadOut, SyntheticPETOut
from backend.config import settings
from backend.knowledge_graph import patient_store
from backend.utils.image_utils import load_mri_image
from backend.utils.logger import get_logger
from backend.utils.validators import validate_image_file

router = APIRouter()
logger = get_logger(__name__)


@router.post("/upload", response_model=ScanUploadOut, status_code=201)
async def upload_mri(
    patient_id: str = Form(...),
    file: UploadFile = File(...),
) -> ScanUploadOut:
    """Upload a brain MRI scan and persist metadata."""
    try:
        validate_image_file(file.filename or "scan.png")

        patient_dir = settings.upload_path / patient_id
        patient_dir.mkdir(parents=True, exist_ok=True)

        dest = patient_dir / f"mri_{file.filename}"
        content = await file.read()
        dest.write_bytes(content)

        visit = patient_store.create_visit(patient_id)
        scan_row = patient_store.save_mri_scan(
            patient_id=patient_id,
            visit_id=visit["visit_id"],
            file_path=str(dest),
        )

        from datetime import datetime, timezone
        return ScanUploadOut(
            scan_id=scan_row["scan_id"],
            patient_id=patient_id,
            file_path=str(dest),
            upload_date=datetime.now(timezone.utc),
        )

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"MRI upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{scan_id}/synthesize", response_model=SyntheticPETOut)
async def synthesize_pet(scan_id: str, patient_id: str = Form(...)) -> SyntheticPETOut:
    """Run GAN inference to synthesize a PET image from the stored MRI scan."""
    try:
        # Look up any scan for this patient matching the requested scan_id
        scan_row = patient_store.get_scan_by_id(scan_id, patient_id)
        if scan_row is None:
            # Fallback: check latest scan
            latest = patient_store.get_latest_scan(patient_id)
            if latest and latest["scan_id"] == scan_id:
                scan_row = latest
        if scan_row is None:
            raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")

        mri_tensor = load_mri_image(scan_row["file_path"], size=settings.gan_image_size)
        result = agent2_pet_synthesizer.run(mri_tensor, patient_id, scan_id)

        pet_row = patient_store.save_synthetic_pet(
            patient_id=patient_id,
            scan_id=scan_id,
            file_path=result["file_path"],
            ssim_score=result["ssim_score"],
            psnr_score=result["psnr_score"],
        )

        from datetime import datetime, timezone
        return SyntheticPETOut(
            pet_id=pet_row["pet_id"],
            scan_id=scan_id,
            patient_id=patient_id,
            file_path=result["file_path"],
            heatmap_file_path=result.get("heatmap_file_path"),
            generated_at=datetime.now(timezone.utc),
            ssim_score=result["ssim_score"],
            psnr_score=result["psnr_score"],
            is_fallback=result.get("is_fallback", True),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"PET synthesis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{patient_id}/all", response_model=list[ScanUploadOut])
async def get_all_scans(patient_id: str) -> list[ScanUploadOut]:
    """Return all uploaded MRI scans for a patient, newest first."""
    try:
        scans = patient_store.get_all_scans(patient_id)
        from datetime import datetime, timezone
        result = []
        for s in scans:
            try:
                upload_date = datetime.fromisoformat(s["created_at"])
            except Exception:
                upload_date = datetime.now(timezone.utc)
            result.append(ScanUploadOut(
                scan_id=s["scan_id"],
                patient_id=patient_id,
                file_path=s["file_path"],
                upload_date=upload_date,
            ))
        return list(reversed(result))  # newest first
    except Exception as e:
        logger.error(f"get_all_scans failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: str,
    patient_id: str = Query(..., description="Owner patient ID"),
) -> dict:
    """Delete an MRI scan record and remove the file from disk."""
    try:
        file_path = patient_store.delete_mri_scan(scan_id, patient_id)
        if file_path is None:
            raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found for patient {patient_id}")
        p = Path(file_path)
        if p.exists():
            p.unlink()
        return {"deleted": True, "scan_id": scan_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{patient_id}/latest", response_model=ScanStatusOut)
async def get_latest_scan(patient_id: str) -> ScanStatusOut:
    """Get the most recent MRI scan and synthetic PET status for a patient."""
    try:
        scan = patient_store.get_latest_scan(patient_id)
        if scan is None:
            raise HTTPException(status_code=404, detail="No scans found for patient")

        return ScanStatusOut(
            scan_id=scan["scan_id"],
            patient_id=patient_id,
            mri_path=scan["file_path"],
            pet_generated=False,  # TODO: check pet table
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"get_latest_scan failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
