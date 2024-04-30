#!/usr/bin/env python
import os, sys
import subprocess
import argparse
from numpy import isin
from termcolor import colored
from pyalpm import Handle
import yaml

CONFIG_PATH = "/etc/rebuild-initramfs.yaml"

# printing helpers
def print_err(s: str) -> None:
    print(s, file=sys.stderr)

def warn(msg: str, use_color: bool=True) -> str:
    return "{} {}".format(colored("WARNING:", "yellow", no_color=not use_color), msg)

def err(msg: str, use_color: bool=True) -> str:
    return "{} {}".format(colored("ERROR:", "red", no_color=not use_color), msg)

def info(msg: str, use_color: bool=True) -> str:
    return "{} {}".format(colored("INFO:", "green", no_color=not use_color), msg)

# misc helpers
def get_ver(files) -> str:
    for (path, _, _) in files:
        if path.startswith("usr/lib/modules/") and path != "usr/lib/modules/":
            return path.rsplit("/")[-2]
    return ""

class Builder(object):
    def __init__(self, use_color: bool=True, dry=False, verbosity=1,
                 build_fallback=False, sudo=True, yes=True, key="", cert=""):
        self.use_color = use_color
        self.dry = dry
        # verbosity 0 = quiet, 1 = normal, >=2 = verbose
        self.verbosity = verbosity
        self.build_fallback = build_fallback
        self.sudo = sudo
        self.yes = yes
        self.key = key
        self.cert = cert
        self.sign = key and cert

    def prompt(self) -> bool:
        if self.yes:
            return True
        while True:
            res = input("Continue (Y/n)? ")
            if res == "Y" or res == "y" or res == "":
                return True
            elif res == "n" or res == "N":
                return False
            else:
                print("Please answer y/Y or n/N!")

    def do_command(self, action: str, cmd: list[str], version: str) -> None:
        if self.sudo:
            cmd.insert(0, "sudo")

        if self.verbosity > 0:
            print("{} {} {}".format(colored("*", "blue", no_color=not self.use_color), action, version))
        if self.verbosity > 1:
            print(info("Running: {}".format(" ".join(cmd)), self.use_color))

        if not self.dry:
            subprocess.run(cmd)
        else:
            print(" ".join(cmd))

    def detect_kernels(self) -> list[str]:
        base = "/usr/lib/modules"
        kernels = []
        for d in os.listdir(base):
            try:
                with open(os.path.join(base, d, "pkgbase")) as f:
                    pkg_name = f.read().strip()
                    kernels.append((pkg_name, d))
            except FileNotFoundError:
                if self.verbosity > 0:
                    print_err(warn("{} is detected, but it is not an installed kernel!".format(d), self.use_color))
        return kernels

    def rebuild_for_base(self, base: str, version: str) -> None:
        if not self.yes:
            print("{} Rebuild initramfs for: {}".format(colored("::", "blue", no_color=not self.use_color), base))

        if not self.prompt():
            if self.verbosity > 1:
                print(info("Not rebuilding initramfs for {}".format(version), self.use_color))
            return

        # Build the initramfs images
        image_path = "/boot/initramfs-{}.img".format(base)
        fallback_path = "/boot/initramfs-{}-fallback.img".format(base)
        cmd = ["dracut", "-f", "--no-hostonly-cmdline", "-H", image_path, "--kver", version]
        fallback_cmd = ["dracut", "-f", "-N", fallback_path,
                        "--kver", version]

        if self.verbosity > 1:
            cmd.insert(1, "-v")
            fallback_cmd.insert(1, "-v")
        elif self.verbosity == 0:
            cmd.insert(1, "-q")
            fallback_cmd.insert(1, "-q")

        self.do_command("Building initramfs for", cmd, version)

        if self.build_fallback:
            self.do_command("Building fallback initramfs for", fallback_cmd, version)

        # Copy the vmlinuz image
        vmlinuz_src_path = "/usr/lib/modules/{}/vmlinuz".format(version)
        vmlinuz_dst_path = "/boot/vmlinuz-{}".format(base)
        copy_cmd = ["install", "-Dm644", vmlinuz_src_path, vmlinuz_dst_path]
        self.do_command("Copying vmlinuz to /boot for", copy_cmd, version)

        # Sign if requested
        if self.sign:
            sign_cmd = ["sbsign", "--key", self.key, "--cert", self.cert, "--output",
                        vmlinuz_dst_path, vmlinuz_dst_path]
            self.do_command("Signing vmlinuz for", sign_cmd, version)

    def rebuild_all(self, rebuild_for: list[str]=[]) -> None:
        if self.verbosity > 1:
            print(info("Running in verbose mode...", self.use_color))

        work_list = []
        if not rebuild_for:
            work_list = self.detect_kernels()
        else:
            try:
                hdl = Handle(".", "/var/lib/pacman")
            except Exception as e:
                print_err(err("Encountered error when reading package database. Possible pacman database corruption.", self.use_color))
                return
            db = hdl.get_localdb()

            for pkg_name in rebuild_for:
                pkg = db.get_pkg(pkg_name)
                if not pkg:
                    print_err(warn("{} is not an installed kernel!".format(pkg_name), self.use_color))
                else:
                    ver = get_ver(pkg.files)
                    work_list.append((pkg_name, ver))

        for (base, ver) in work_list:
            self.rebuild_for_base(base, ver)


def main():
    parser = argparse.ArgumentParser(description="Rebuild some (or all) initramfs images using Dracut.")
    parser.add_argument("-y", "--yes", action="store_true", help="Say \"yes\" to all questions")
    parser.add_argument("-v", "--verbose", action="store_true", help="Be more verbose")
    parser.add_argument("-q", "--quiet", action="store_true", help="Be quiet. This is obviously mutually exclusive with '-v'")
    parser.add_argument("-k", "--hook", action="store_true", help="""
Enable hook (i.e., non-interactive) mode. This will suppress some warnings and also implies '-y'. DO NOT USE if you intend
to run this program in interactive mode and not as part of a script!""")
    parser.add_argument("--key", metavar="KEY_FILE", help="Machine Owner Key (MOK) used to sign kernel image for Secure Boot")
    parser.add_argument("--cert", metavar="CERT_FILE", help="MOK certificate used to sign kernel image for Secure Boot")
    parser.add_argument("--no-colors", action="store_true", help="Don't use colors")
    parser.add_argument("--build-fallback", action="store_true", help="Build fallback initramfs images")
    parser.add_argument("--no-fallback", action="store_true", help="Don't build fallback initramfs images")
    parser.add_argument("--dry", action="store_true", help="Dry run. Print the commands that will be executed, instead of executing them. \
                        This is useful for debugging.")
    # Used only for debugging and testing
    parser.add_argument("--config", help=argparse.SUPPRESS)
    parser.add_argument("kernels", nargs="*", metavar="kernel package names")

    # Parse all the command-line arguments
    args = parser.parse_args()

    # set the default values
    verbosity = 1
    key = ""
    cert = ""
    build_fallback = False
    yes = False
    no_colors = args.no_colors
    config_path = args.config if args.config else CONFIG_PATH
    hook = args.hook
    root = os.geteuid() == 0

    if root and not hook:
        print_err(warn("You are running this script as root. This is not recommended, unless you are running it in a pacman hook.\
                        The program will automatically call out to sudo when required.", not no_colors))

    # Try to parse the config file
    try:
        with open(config_path) as f:
            config = yaml.safe_load(f)
            # This must be checked because of quirks in PyYAML:
            # if the file is empty or malformed, it will return None or a string,
            # rather than the empty dictionary or throw an exception as is reasonable.
            # Bad design in my opinion, but we have to work with it.
            if config and not isinstance(config, str):
                verbosity = 2 if config.get("verbose", False) else 1
                key = config.get("key_path", "")
                cert = config.get("cert_path", "")
                build_fallback = config.get("build_fallback", False)
    except FileNotFoundError:
        print_err(warn("Configuration file not found!".format(CONFIG_PATH), not no_colors))

    # Command-line args always override config file
    if args.quiet:
        verbosity = 0
    elif args.verbose:
        verbosity = 2

    if (not key and cert) or (key and not cert):
        print_err(warn("Path to MOK key and certified must be both specified in order to sign the kernel image! \
                        Not signing.", not args.no_colors))
    elif args.key and args.cert:
        key = args.key
        cert = args.cert

    yes = args.yes or hook
    build_fallback = args.build_fallback or build_fallback if not args.no_fallback else False
    builder = Builder(not no_colors, args.dry, verbosity, build_fallback, not root, yes, key, cert)

    try:
        builder.rebuild_all(args.kernels)
    except KeyboardInterrupt: # Catch Ctrl-C to be killed gracefully
        sys.exit(1)

if __name__ == "__main__":
    main()