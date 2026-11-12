#!/usr/bin/env python3
"""Package an independently modified GPL build; optionally notarize and staple it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '11.10.1'
IDENTITY = 'Developer ID Application: XI ZHANG (3L3BB9SDCS)'
NAME = f'AltTab-{VERSION}-SelfBuild-universal'
OUT = ROOT / 'build/distribution' / f'{VERSION}-selfbuild.1'
STAGE = OUT / 'stage'
MACHO = {bytes.fromhex(x) for x in ('feedface', 'cefaedfe', 'feedfacf', 'cffaedfe', 'cafebabe', 'bebafeca', 'cafebabf', 'bfbafeca')}


def run(*args, **kwargs):
    print('Running:', ' '.join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def sign(path, app=False):
    args = ['codesign', '--force', '--sign', IDENTITY, '--timestamp', '--options', 'runtime']
    if app:
        args += ['--entitlements', str(ROOT / 'alt_tab_macos.entitlements')]
    run(*args, path)


def notarize(path, profile, name):
    result = run('xcrun', 'notarytool', 'submit', path, '--keychain-profile', profile,
                 '--wait', '--timeout', '15m', '--output-format', 'json', capture_output=True, text=True)
    (OUT / f'{name}-notarization.json').write_text(result.stdout)
    data = json.loads(result.stdout)
    print('Notarization:', data.get('status'), data.get('id'), flush=True)
    if data.get('status') != 'Accepted':
        run('xcrun', 'notarytool', 'log', data['id'], '--keychain-profile', profile,
            OUT / f'{name}-notarization-issues.json')
        raise SystemExit('Apple did not accept this submission; inspect the saved diagnostics.')
    run('xcrun', 'stapler', 'staple', path)
    run('xcrun', 'stapler', 'validate', path)
    return data['id']


def sources(destination):
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    paths = {Path(p) for p in tracked if p}
    paths.update(map(Path, ['SELF-BUILD.md', 'scripts/package_self_build.py', 'config/local.xcconfig']))
    paths.update(p.relative_to(ROOT) for p in (ROOT / 'distribution').rglob('*') if p.is_file())
    # General-purpose packaging tools are available from Xcode/Homebrew; they are not app source.
    paths -= {Path('scripts/notarytool'), Path('scripts/xcbeautify')}
    with tarfile.open(destination, 'w:gz') as archive:
        for relative in sorted(paths):
            path = ROOT / relative
            if path.is_file() or path.is_symlink():
                archive.add(path, arcname=f'AltTab-{VERSION}-SelfBuild-Source/{relative}', recursive=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--notary-profile')
    args = parser.parse_args()
    os.chdir(ROOT)
    original = ROOT / 'DerivedData/Build/Products/Release/AltTab.app'
    info = plistlib.loads((original / 'Contents/Info.plist').read_bytes())
    if info['CFBundleShortVersionString'] != VERSION:
        raise SystemExit('Build the matching Release version first.')
    OUT.mkdir(parents=True, exist_ok=True)
    if STAGE.exists():
        shutil.rmtree(STAGE)
    STAGE.mkdir()
    app = STAGE / 'AltTab.app'
    run('ditto', original, app)
    resources = app / 'Contents/Resources'
    shutil.copy2(ROOT / 'SELF-BUILD.md', resources / 'SELF-BUILD.md')
    shutil.copy2(ROOT / 'LICENCE.md', resources / 'SELF-BUILD-LICENCE.txt')
    licenses = resources / 'Third-Party-Licenses'
    licenses.mkdir()
    for path in (ROOT / 'distribution/third-party').glob('*-LICENSE.txt'):
        shutil.copy2(path, licenses / path.name)
    nested = []
    for path in (app / 'Contents').rglob('*'):
        if path.is_symlink():
            continue
        if path.is_file():
            with path.open('rb') as stream:
                if stream.read(4) in MACHO and path != app / 'Contents/MacOS/AltTab':
                    nested.append(path)
        elif path.suffix in {'.app', '.xpc', '.framework'}:
            nested.append(path)
    for path in sorted(nested, key=lambda p: len(p.parts), reverse=True):
        sign(path)
    sign(app, app=True)
    run('codesign', '--verify', '--deep', '--strict', '--verbose=2', app)
    architectures = subprocess.check_output(['lipo', '-archs', str(app / 'Contents/MacOS/AltTab')], text=True).split()
    if not {'arm64', 'x86_64'}.issubset(architectures):
        raise SystemExit('The application must contain both arm64 and x86_64 slices.')
    submissions = {}
    if args.notary_profile:
        archive = OUT / f'{NAME}-notary.zip'
        run('ditto', '-c', '-k', '--keepParent', app, archive)
        result = run('xcrun', 'notarytool', 'submit', archive, '--keychain-profile', args.notary_profile,
                     '--wait', '--timeout', '15m', '--output-format', 'json', capture_output=True, text=True)
        (OUT / 'app-notarization.json').write_text(result.stdout)
        report = json.loads(result.stdout)
        if report.get('status') != 'Accepted':
            run('xcrun', 'notarytool', 'log', report['id'], '--keychain-profile', args.notary_profile,
                OUT / 'app-notarization-issues.json')
            raise SystemExit('App notarization was not accepted.')
        submissions['app'] = report['id']
        run('xcrun', 'stapler', 'staple', app)
        run('xcrun', 'stapler', 'validate', app)
        run('spctl', '--assess', '--type', 'execute', '--verbose=2', app)
    sources(STAGE / f'AltTab-{VERSION}-SelfBuild-Source.tar.gz')
    shutil.copy2(ROOT / 'SELF-BUILD.md', STAGE / 'README.md')
    shutil.copy2(ROOT / 'LICENCE.md', STAGE / 'LICENSE.txt')
    (STAGE / '安装说明.txt').write_text(
        '将 AltTab.app 拖入 Applications。首次使用需授予控制权限和屏幕录制权限。\n'
        f'这是基于 AltTab {VERSION} 的独立修改版，由 XI ZHANG 于 2026-10-29 制作，并非官方发行版。\n'
        '修改说明见 README.md，GPL 许可证见 LICENSE.txt，完整对应源码包含在 Source.tar.gz 压缩包中。\n'
        '本版本停用官方自动更新，后续更新需要重新编译分发。\n', encoding='utf-8')
    (STAGE / 'Applications').symlink_to('/Applications', target_is_directory=True)
    dmg = OUT / f'{NAME}-signed-unnotarized.dmg'
    run('hdiutil', 'create', '-volname', f'AltTab {VERSION} Self Build', '-srcfolder', STAGE, '-format', 'UDZO', '-ov', dmg)
    run('codesign', '--force', '--sign', IDENTITY, '--timestamp', dmg)
    run('codesign', '--verify', '--strict', '--verbose=2', dmg)
    if args.notary_profile:
        submissions['dmg'] = notarize(dmg, args.notary_profile, 'dmg')
        run('spctl', '--assess', '--type', 'open', '--context', 'context:primary-signature', '--verbose=2', dmg)
        final = OUT / f'{NAME}.dmg'
        dmg.replace(final)
        dmg = final
    digest = hashlib.sha256(dmg.read_bytes()).hexdigest()
    (OUT / 'SHA256SUMS.txt').write_text(f'{digest}  {dmg.name}\n')
    report = {'version': VERSION, 'team': '3L3BB9SDCS', 'architectures': ['arm64', 'x86_64'],
              'notarized': bool(args.notary_profile), 'submissions': submissions, 'sha256': digest, 'file': str(dmg)}
    (OUT / 'release-info.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
