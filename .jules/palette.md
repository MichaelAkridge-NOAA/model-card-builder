# Palette's Journal - Critical UX/Accessibility Learnings

This journal tracks critical UX and accessibility insights discovered during the development of the Model Card Builder.

## 2025-05-14 - Enhancing Keyboard Navigation for Card-Based Layouts
**Learning:** For card-based interfaces where the entire card is a logical unit but only a subset (like a "View" link) is interactive, using `:focus-within` on the card container provides a much clearer visual indicator for keyboard users than a standard outline on the link alone. Combining this with a "Skip to Content" link significantly improves the experience for users relying on assistive technology.
**Action:** Always implement `:focus-within` styles and "Skip to Content" links when building navigational galleries or dashboard interfaces.
