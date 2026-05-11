## 2025-05-14 - Skip Links and Focus-Within for Gallery Accessibility
**Learning:** For card-based layouts where the primary interaction is a nested link, using `:focus-within` on the card container provides superior visual feedback for keyboard users compared to focusing the link alone. Additionally, 'Skip to Content' links must always have a matching target ID on the primary `<main>` element to be functional.
**Action:** Always implement `:focus-within` on card components and ensure skip link targets are correctly identified in the DOM.
