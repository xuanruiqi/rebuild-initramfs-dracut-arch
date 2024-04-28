#!/usr/bin/env python
import os, sys
import subprocess
import argparse
from termcolor import colored
from pyalpm import Handle
import yaml

CONFIG_PATH = "/etc/rebuild-initramfs.yaml"
use_color = True

class ColorPrinter(object):
    def __init__(self, use_color=True):
        self.use_color = use_color

    def color(self, s: str, color: str) -> str:
        if self.use_color:
            return colored(s, color)
        else:
            return s
    
    def warn(self, msg: str) -> str:
        return "{} {}".format(self.color("WARNING:", "yellow"), msg)
    
    def err(self, msg: str) -> str:
        return "{} {}".format(self.color("ERROR:", "red"), msg)
    
    def info(self, msg: str) -> str:
        return "{} {}".format(self.color("INFO:", "green"), msg)

def print_err(s: str) -> None:
    print(s, file=sys.stderr)

def prompt() -> bool:
    while True:
        res = input("Continue (Y/n)? ")
        if res == "Y" or res == "y" or res == "":
            return True
        elif res == "n" or res == "N":
            return False
        else:
            print("Please answer y/Y or n/N!")

def do_command(action: str, pr: ColorPrinter, cmd: list[str], version: str, verbosity: int=1) -> None:
    # verbosity 0 = quiet, 1 = normal, >2 = verbose
    if verbosity > 0:
        print("{} {} {}".format(pr.color("*", "blue"), action, version))
    if verbosity > 1:
        print(pr.info("Running: {}".format(" ".join(cmd))))
    subprocess.run(cmd)        

def rebuild_for_base(base: str, version: str,
                     pr: ColorPrinter,
                     sudo: bool=True,
                     yes: bool=False,
                     verbosity: int=1,
                     build_fallback: bool=False,
                     sign: bool=False,
                     sb_key: str="",
                     sb_cert: str="") -> None:
    if not yes:
        if verbosity > 0:
            print("{} Rebuild initramfs for: {}".format(pr.color("::", "blue"), base))
        
        if not prompt():
            if verbosity > 1:
                print(pr.info("Not rebuilding initramfs for {}".format(version)))
            return

    # Build the initramfs images
    image_path = "/boot/initramfs-{}.img".format(base)
    fallback_path = "/boot/initramfs-{}-fallback.img".format(base)

    cmd = ["dracut", "-f", "--no-hostonly-cmdline", "-H", image_path,
           "--kver", version]
    fallback_cmd = ["dracut", "-f", "-N", fallback_path,
                    "--kver", version]

    if verbosity > 1:
        cmd.insert(1, "-v")
        fallback_cmd.insert(1, "-v")
    if verbosity == 0:
        cmd.insert(1, "-q")
        fallback_cmd.insert(1, "-q")
    if sudo:
        cmd.insert(0, "sudo")
        fallback_cmd.insert(0, "sudo")

    do_command("Building initramfs for", pr, cmd, version, verbosity)

    if build_fallback:
        do_command("Building fallback initramfs for", pr, fallback_cmd, version, verbosity)

    # Copy the vmlinuz image
    vmlinuz_src_path = "/usr/lib/modules/{}/vmlinuz".format(version)
    vmlinuz_dst_path = "/boot/vmlinuz-{}".format(base)
    copy_cmd = ["install", "-Dm644", vmlinuz_src_path, vmlinuz_dst_path]

    if sudo:
        copy_cmd.insert(0, "sudo")

    do_command("Copying vmlinuz to /boot for", pr, copy_cmd, version, verbosity)

    # Sign if requested
    if sign:
        assert sb_key != ""
        assert sb_cert != ""
        
        sign_cmd = ["sbsign", "--key", sb_key, "--cert", sb_cert, "--output",
                    vmlinuz_dst_path, vmlinuz_dst_path]
        if sudo:
            sign_cmd.insert(0, "sudo")

        do_command("Signing vmlinuz for", pr, sign_cmd, version, verbosity)

def get_ver(files) -> str:
    for (path, _, _) in files:
        if path.startswith("usr/lib/modules/") and path != "usr/lib/modules/":
            return path.rsplit("/")[-2]

def rebuild_all(pr: ColorPrinter,
                rebuild_for: list[str]=[],
                yes: bool=False,
                verbosity: int=1,
                hook: bool=False,
                build_fallback: bool=False,
                sb_key: str="",
                sb_cert: str="") -> None:
    is_root = os.geteuid() == 0
    if is_root and not hook:
        print_err(pr.warn(
            "Don't run this script with root privileges, unless you're running it in a pacman hook! Calls to sudo will be inserted."))

    if verbosity > 1:
        print(pr.info("Running in verbose mode..."))

    sign = False
    if sb_key and sb_cert:
        sign = True
    elif sb_key or sb_cert:
        print_err(pr.err("Must provide both key and certificate path to sign images!"))
        sys.exit(1)

    work_list = []
    if not rebuild_for:
        base = "/usr/lib/modules"
        for d in os.listdir(base):
            try:
                with open(os.path.join(base, d, "pkgbase")) as f:
                    pkg_name = f.read().strip()
                    work_list.append((pkg_name, d))
            except FileNotFoundError:
                print_err(pr.warn("{} is detected, but it is not an installed kernel!".format(pkg_name)))            
    else:
        try:
            hdl = Handle(".", "/var/lib/pacman")
        except e:
            print_err(pr.err("Encountered error when reading package database. Possible pacman database corruption."))
            sys.exit(1)
        db = hdl.get_localdb()

        for pkg_name in rebuild_for:
            pkg = db.get_pkg(pkg_name)
            if not pkg:
                print_err(pr.warn("{} is not an installed kernel!".format(pkg_name)))
            else:
                ver = get_ver(pkg.files)
                work_list.append((pkg_name, ver))
    
    for (base, ver) in work_list:
        rebuild_for_base(base, ver, pr, sudo=not is_root, yes=yes, verbosity=verbosity, build_fallback=build_fallback, sign=sign, sb_key=sb_key, sb_cert=sb_cert)


def main():
    parser = argparse.ArgumentParser(description="Rebuild some (or all) initramfs images using Dracut.")
    parser.add_argument("-y", "--yes", action="store_true", help="Say \"yes\" to all questions")
    parser.add_argument("-v", "--verbose", action="store_true", help="Be more verbose")
    parser.add_argument("-q", "--quiet", action="store_true", help="Be quiet. This is obviously mutually exclusive with '-v'")
    parser.add_argument("-k", "--hook", action="store_true", help="""
Enable hook (i.e., non-interactive) mode. This will suppress some warnings and also implies '-y'. DO NOT USE if you intend
to run this program in interactive mode!""")
    parser.add_argument("--key", metavar="KEY_FILE", help="Machine Owner Key (MOK) used to sign kernel image for Secure Boot")
    parser.add_argument("--cert", metavar="CERT_FILE", help="MOK certificate used to sign kernel image for Secure Boot")
    parser.add_argument("--no-colors", action="store_true", help="Don't use colors")
    parser.add_argument("--build-fallback", action="store_true", help="Build fallback initramfs images")
    parser.add_argument("--no-fallback", action="store_true", help="Don't build fallback initramfs images")
    parser.add_argument("kernels", nargs="*", metavar="kernel package names")

    verbosity = 1
    key = ""
    cert = ""
    build_fallback = False
    yes = False

    try:
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
            verbosity = 2 if config.get("verbose", False) else 1
            key = config.get("key_path", "")
            cert = config.get("cert_path", "")
            build_fallback = config.get("build_fallback", False)
    except FileNotFoundError:
        pass

    # Command-line args always override config file
    args = parser.parse_args()
    if args.quiet:
        verbosity = 0
    elif args.verbose:
        verbosity = 2
        
    if args.key:
        key = args.key
    if args.cert:
        cert = args.cert

    yes = args.yes or args.hook
    build_fallback = args.build_fallback or build_fallback if not args.no_fallback else False
    pr = ColorPrinter(use_color=not args.no_colors)
    rebuild_all(pr, args.kernels, yes, verbosity, args.hook, build_fallback, key, cert)

if __name__ == "__main__":
    main()