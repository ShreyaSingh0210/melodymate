# NVDA test checklist: MelodyMate singing page

Test with NVDA running, keyboard only, in Chrome or Edge at http://127.0.0.1:8000. Wear headphones.

1. Page load: NVDA reads the title "MelodyMate singing practice". Pressing H moves through one level 1 heading and three level 2 headings in order.
2. Tab order: Melody, How strictly to compare, headphones checkbox, Play reference melody, Start recording, Stop and analyze. Nothing else takes focus.
3. Each control is announced with its name and type. The checkbox says checked or not checked. Start recording and Stop and analyze say unavailable when they cannot be used.
4. Press Start recording before ticking the box. Expect the status message about headphones, and focus stays on the button.
5. Tick the box. Start recording no longer says unavailable.
6. Press Play reference melody. The melody plays only after the press. The status says it is playing and later that it finished. Each message is spoken once.
7. Press Start recording. The browser asks for microphone permission (first time only). After you allow it, the status says recording has started. Focus has not moved.
8. Sing, then press Stop and analyze. The status says it is analyzing, then reads the result: score first, then problems, then "Notes heard".
9. Deny microphone permission once. Expect a clear message, and the page stays usable.
10. Press Escape, resize the window, zoom to 200 percent. Nothing is cut off, and nothing needs a mouse.

When something fails, write down: the step number, what NVDA said, what you expected, the browser and its version, and whether you were wearing headphones.
