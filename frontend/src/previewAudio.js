// Shared singleton so only one hover preview plays at a time across all views.
let _preview = null;
let _playerPlaying = false;

export function setPlayerPlaying(val) {
  _playerPlaying = val;
}

export function playPreview(url) {
  if (_playerPlaying) return; // player has precedence while actively playing
  stopPreview();
  const audio = new Audio(url);
  audio.volume = 0.5;
  audio.play().catch(() => {});
  _preview = audio;
}

export function stopPreview() {
  if (_preview) {
    _preview.pause();
    _preview.currentTime = 0;
    _preview = null;
  }
}
