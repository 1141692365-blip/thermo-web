@@
     df = df.rename(columns=colmap)
-    if 'Seebeck_V_per_K' in df.columns:
-        s_med = df['Seebeck_V_per_K'].abs().median(skipna=True)
-        if pd.notna(s_med) and s_med > 1.0:
-            df['Seebeck_V_per_K'] = df['Seebeck_V_per_K'] * 1e-6
+    if 'Seebeck_V_per_K' in df.columns:
+        # robust median calculation: ensure scalar value
+        try:
+            s = df['Seebeck_V_per_K'].abs()
+            if isinstance(s, (pd.Series, np.ndarray)):
+                s_med = float(np.nanmedian(s.to_numpy()))
+            else:
+                s_med = float(s)
+        except Exception:
+            s_med = np.nan
+
+        # if median unusually large, assume micro->V conversion needed
+        if not np.isnan(s_med) and s_med > 1.0:
+            try:
+                df['Seebeck_V_per_K'] = pd.to_numeric(df['Seebeck_V_per_K'], errors='coerce') * 1e-6
+            except Exception:
+                # fallback: attempt elementwise conversion
+                df['Seebeck_V_per_K'] = df['Seebeck_V_per_K'].apply(lambda x: float(x)*1e-6 if pd.notna(x) else x)
+        # if after conversion column has strange shape (e.g., nested lists), flatten to numeric series
+        if hasattr(df['Seebeck_V_per_K'].iloc[0], '__len__') and not isinstance(df['Seebeck_V_per_K'].iloc[0], (str, bytes)):
+            # replace with first element of each entry
+            try:
+                df['Seebeck_V_per_K'] = df['Seebeck_V_per_K'].apply(lambda v: v[0] if (v is not None and len(v)>0) else np.nan)
+                df['Seebeck_V_per_K'] = pd.to_numeric(df['Seebeck_V_per_K'], errors='coerce')
+            except Exception:
+                pass
*** End Patch