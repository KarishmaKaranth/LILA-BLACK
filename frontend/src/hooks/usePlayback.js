import { useEffect, useRef, useState } from "react";

export function usePlayback(durationMs) {
  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const rafRef = useRef(0);
  const lastRef = useRef(0);

  useEffect(() => {
    setCurrentTime(0);
    setIsPlaying(false);
  }, [durationMs]);

  useEffect(() => {
    if (!isPlaying) return undefined;
    lastRef.current = performance.now();

    const step = (now) => {
      const delta = now - lastRef.current;
      lastRef.current = now;
      setCurrentTime((prev) => {
        const next = prev + delta * speed;
        if (next >= durationMs) {
          setIsPlaying(false);
          return durationMs;
        }
        return next;
      });
      rafRef.current = requestAnimationFrame(step);
    };

    rafRef.current = requestAnimationFrame(step);
    return () => cancelAnimationFrame(rafRef.current);
  }, [isPlaying, speed, durationMs]);

  return {
    currentTime,
    isPlaying,
    speed,
    setCurrentTime,
    setIsPlaying,
    setSpeed,
    togglePlay: () => setIsPlaying((p) => !p),
    reset: () => {
      setCurrentTime(0);
      setIsPlaying(false);
    },
  };
}
