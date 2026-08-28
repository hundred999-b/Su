# ShopU local upgrade build

Base: uploaded `shopu_support.zip`

Included:
- Existing full ShopU project and support system preserved.
- Previous Mini App UI upgrade retained.
- Product detail experience retained.
- Seller verification/rating/review summary retained.
- Buyer review list added to seller/product detail.
- Buyer review form added to Orders.
- Backend review eligibility strengthened:
  - completed orders are reviewable;
  - disputed orders are locked while unresolved;
  - refunded orders are reviewable only when a dispute was explicitly resolved in buyer's favor;
  - ordinary refunds are not reviewable;
  - only the buyer can review;
  - one review per order.
- Dispute settlement integration records explicit resolution events when a disputed escrow is released (seller-favor) or refunded (buyer-favor).
- Existing support app is preserved; no support models were rewritten.

Static verification performed:
- Modified Python files parse successfully with Python AST.
- Mini App JavaScript passes `node --check`.
- Full Django tests were NOT run in this build environment because Django is not installed here.

Important:
- This ZIP is for LOCAL TESTING FIRST.
- Do not deploy to Render until the local Django check and full test suite are green.
- Do not point local testing at production unless you intentionally choose to do so.
