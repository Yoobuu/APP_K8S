from .context import CollectorContext


def collect(context: CollectorContext):
    diagnostics = context.diagnostics
    logger = context.logger

    try:
        content = context.content
        license_manager = content.licenseManager
        if not license_manager:
            return []
        
        licenses = license_manager.licenses
    except Exception as exc:
        diagnostics.add_error("vLicense", "fetch", exc)
        logger.error("Fallo fetching vLicense: %s", exc)
        return []

    rows = []
    for lic in licenses:
        diagnostics.add_attempt("vLicense")
        try:
            name = lic.name
            key = lic.licenseKey
            total = lic.total
            used = lic.used
            cost_unit = lic.costUnit
            
            # Expiration
            expiration = ""
            # Some versions might have properties differently or via properties dict
            # Check properties for expiration
            if lic.properties:
                for prop in lic.properties:
                    if prop.key == "expirationDate":
                        expiration = str(prop.value)
            
            # Labels/Features
            labels = ""
            if lic.labels:
                labels = ", ".join([f"{l.key}={l.value}" for l in lic.labels])
            
            # Features is usually a map of feature keys
            features = ""
            # Not iterating features to avoid clutter, usually Product name is enough which is mapped to Name
            
            rows.append({
                "Name": name,
                "LicenseKey": key,
                "Total": total,
                "Used": used,
                "Expiration": expiration,
                "Product": labels, # Mapping labels to Product/Labels column
                "Unit": cost_unit,
                "Status": "", 
                "AssetTag": ""
            })
            diagnostics.add_success("vLicense")
        except Exception as exc:
            diagnostics.add_error("vLicense", lic.licenseKey, exc)

    return rows