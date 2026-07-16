# Style application contract

Style profiles are resolved into JSON and then applied to the `VisualSpec` theme with `scripts/apply_style_profile.py`. The script writes both the styled spec and a `style_application.v1` report containing the profile identifier, source hash, and keys actually applied. A style profile that cannot map to renderer settings is reported as `no_compatible_settings`; it is never described as applied merely because it was selected.
