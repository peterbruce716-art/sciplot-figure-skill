# v2.5.1 Stable Branch Freeze Policy

## Allowed After v2.5.1

- Bug fixes.
- Security fixes.
- Dependency compatibility fixes.
- Error message improvements.
- Test additions.
- Documentation corrections.
- Performance improvements that do not change output semantics.

## Not Changed On The Stable Branch

- VisualSpec v2 field meanings.
- Manifest v2 status meanings.
- `strict` / `near` / `not_strict` decision semantics.
- Existing plot type default drawing behavior.
- Existing output directory structure.
- Existing CLI argument meanings.

## New Requirements

Prefer a project-level custom Python renderer plus the existing QA, bundle, manifest, checksum, and portability gates for complex or new figure types.

Breaking changes belong in VisualSpec v3, Manifest v3, and Skill v3.x.
