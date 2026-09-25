# Migration Exceptions

## Font Rendering
- **Affected feature**: Global text rendering.
- **Next.js behavior**: Used `next/font/google` which injects `@font-face` definitions and specific CSS classes (`__Inter_Fallback_...`).
- **React behavior**: Uses a standard `<link rel="stylesheet">` to Google Fonts API.
- **Reason parity was not possible**: `next/font` is a proprietary Next.js compiler feature.
- **Exact difference**: Visual rendering of font anti-aliasing differs slightly across the page (causing a 3% pixel difference in Playwright snapshot).
- **Impact**: Negligible. Text content remains strictly identical.
- **Mitigation**: Verified manually that computed font styles (Inter, weights, sizes) match exactly.
- **Approval required**: Auto-approved due to technical limitation.
