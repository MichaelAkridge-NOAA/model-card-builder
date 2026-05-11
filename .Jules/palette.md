## 2025-05-15 - [Escaping f-strings in Python generators]
**Learning:** When using Python f-strings to generate HTML that contains CSS or JavaScript, curly braces `{}` and template literals `${}` must be double-escaped `{{ }}` and `${{ }}` respectively. Failing to do so causes a `SyntaxError` when the Python script is executed.
**Action:** Always verify generated code by running the generator script immediately after modifications, especially when injecting JS/CSS into f-string templates.

## 2025-05-15 - [Model Gallery Accessibility]
**Learning:** Adding `:focus-within` to container elements (like model cards) ensures that keyboard users navigating via links inside the container receive the same visual feedback as mouse users on hover. Descriptive `aria-label`s on repetitive "View More" style links provide essential context for screen reader users.
**Action:** Implement container-level focus indicators and context-rich ARIA labels for all interactive grid components.
