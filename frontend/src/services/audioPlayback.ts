export function pauseAllAudio(except?: HTMLAudioElement): void {
  document.querySelectorAll('audio').forEach((audio) => {
    if (audio !== except) audio.pause()
  })
}
