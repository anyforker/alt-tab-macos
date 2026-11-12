# AltTab Self Build 11.10.1

Modified by XI ZHANG on 2026-10-29, based on upstream tag v11.10.1 (c500294b):
https://github.com/lwouis/alt-tab-macos
This is an independently modified GPL-3.0 build, not an official AltTab release.
Upstream authors retain their copyrights. See LICENCE.md and distribution/third-party.

## Modifications

SELF_BUILD enables all local features without purchased license activation or remote
validation. Permission setup does not start a Pro trial. Existing license data is
preserved. Settings identifies this as Self Build rather than purchased Pro activation.
The official Sparkle updater is disabled to prevent replacement by official binaries.

## Building

Requires macOS and Xcode. Dependencies are vendored. config/local.xcconfig selects
arm64 + x86_64, SELF_BUILD and the distributor's Developer ID certificate.

```sh
cp config/self-build.xcconfig config/local.xcconfig
xcodebuild -project alt-tab-macos.xcodeproj -scheme Release -configuration Release \
  -destination 'generic/platform=macOS' -derivedDataPath DerivedData
python3 scripts/package_self_build.py
```

Without that signing certificate, build using your own identity or override with
CODE_SIGN_IDENTITY=- 'OTHER_CODE_SIGN_FLAGS=--timestamp=none' for ad-hoc local use.
The packager signs nested components and the DMG with Developer ID and secure timestamps.
It embeds licenses and modification notices in the DMG and creates the matching source archive beside it.
Credentials and private keys are never included.

To notarize and staple both the app and DMG using credentials already saved in Keychain:

```sh
python3 scripts/package_self_build.py --notary-profile AltTab-Notary
```

Without --notary-profile, output is explicitly named signed-unnotarized.dmg. Such a
file must not be presented as notarized. A final DMG is produced only after Apple's
acceptance, stapling and Gatekeeper checks succeed.

## Installation and redistribution

Drag AltTab.app to Applications. Keep bundle ID com.lwouis.alt-tab-macos and Developer
ID team stable for subsequent updates. Changing from an upstream- or ad-hoc-signed
build may require reauthorizing Accessibility and Screen Recording once. Preferences
are retained; no license-key migration is performed. Automatic upstream updates are
disabled. Future updates require rebuilding and distributing a new signed package.

Keep this notice and the GPL license. Distribute the corresponding source archive alongside the DMG. Recipients may use, modify and redistribute covered code under
GPL-3.0. This build comes without warranty. Do not present it as an official release.
