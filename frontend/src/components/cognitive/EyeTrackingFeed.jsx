import Webcam from 'react-webcam'

export default function EyeTrackingFeed({ active = true }) {
  if (!active) return null
  return (
    <div className="relative w-40 h-32 rounded-md overflow-hidden border border-border bg-black">
      <Webcam
        className="w-full h-full object-cover"
        mirrored
        videoConstraints={{ width: 160, height: 128, facingMode: 'user' }}
      />
      <div className="absolute top-1 left-1 flex items-center gap-1">
        <div className="w-1.5 h-1.5 rounded-full bg-danger animate-pulse" />
        <span className="text-xs text-white/70">Eye track</span>
      </div>
    </div>
  )
}
