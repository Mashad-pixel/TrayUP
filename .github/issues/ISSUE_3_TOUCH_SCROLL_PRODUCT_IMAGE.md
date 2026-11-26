# Issue 3: Swiping vertically over food gallery image on mobile blocks page scroll

## Problem Description
On mobile devices, when viewing a dish detail page (`product.html`), if a user starts a vertical swipe gesture while their finger is touching the dish photo/gallery, the page does not scroll down. The page appears frozen/stuck until they find an area outside the image to scroll from.

## Root Cause
In `frontend/css/student.css`, `.product-gallery-track` had `touch-action: pan-x; overflow-y: hidden;`.
In mobile web specifications, `touch-action: pan-x` informs the browser that the element only permits horizontal gestures and explicitly suppresses the browser's default vertical panning (`pan-y`) when the touch start event occurs inside the element.

## Expected Behavior
- Users must be able to swipe up and down over the food image to scroll down the page naturally.
- Horizontal swipe to navigate photo slides should still work.

## Solution
Update `touch-action` on `.product-gallery-track` to `touch-action: pan-x pan-y;` (or remove the vertical restriction).
