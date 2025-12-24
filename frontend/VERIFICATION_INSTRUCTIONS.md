
# PROPERTIES INTEGRATION VERIFICATION

**1. Core Service Status** (Background)
Ensure Core is running on Port 3010.
Mock endpoint: `http://localhost:3010/api/v1/assets/ASSET-MOCK-1`

**2. Properties Frontend**
Run the frontend:
```bash
cd frontend
npm run dev
```

**3. Verification URL**
Visit: `http://localhost:3000/dashboard/properties/ASSET-MOCK-1`

**Expected Outcome:**
1. Page loads cleanly (no 404).
2. Header shows "ASSET ID: ASSET-MOCK-1" and generic "Address Unknown" (since legacy DB missing).
3. **Universal Dashboard** renders 3 widgets:
   - **Valuation:** Shows $50,000.00 (or similar from mock fixture).
   - **Custody:** Shows Custodian.
   - **Timeline:** Shows "ANCHOR_REGISTERED".
4. Console logs "Core Fetch Failed" IF Core is down (showing "Asset Truth Offline" banner).
   OR logs success if Core is up.
