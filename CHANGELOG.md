# Changes

## Native effort panel: theme and zoom support

- Match both dark- and light-theme control icons.
- Detect common app zoom factors and remember the successful scale.
- Scale the native button target and slider detection together.
- Avoid treating a plain white background as an already-open slider.
- Keep the existing dial direction, volume controls, and shortcut behavior.

Verified against the supplied light-theme reference, existing dark-theme captures, and the live app at 120% zoom. The adapter does not change the app theme or move the physical pointer.
