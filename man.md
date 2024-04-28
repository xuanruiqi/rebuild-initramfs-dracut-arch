rebuild-initramfs(1) -- command-line utility to rebuild multiple kernels at once on Arch-based systems
======================================================================================================

## SYNOPSIS
    rebuild-initramfs [OPTIONS] [<kernel package names>]

## DESCRIPTION
**rebuild-initramfs** is a command-line utility to automate initramfs image creation with `dracut`(8)
on Arch Linux systems.

## USAGE
This will rebuild the initramfs image for all kernels versions installed as `pacman`(8) packages. By 
default, the utility will ask before rebuilding for each kernel version found, and call `sudo`(8) 
when necessary:

    $ rebuild-initramfs

This will rebuild only the initramfs image for the "linux" kernel, i.e. the kernel installed as the "linux" package:

    $ rebuild-initramfs linux

This will rebuild the initramfs image for the "linux" and "linux-lts" kernels:

    $ rebuild-initramfs linux linux-lts

This will rebuild the initramfs image for the "linux" kernel and sign the kernel image using *MOK.key* and *MOK.crt*:

    $ rebuild-initramfs --key MOK.key --cert MOK.crt linux

## OPTIONS

* `-y`, `--yes`: always say "yes" to prompts. This will cause all initramfs images to be rebuilt automatically for all 
specified kernel versions.
* `-v`, `--verbose`: enter verbose mode, that is print more information to the console, which might be useful for debugging
and other purposes.
* `-q`, `--quiet`: enter quiet mode. This will cause less information to be printed to the console, and will also pass the
`-q` option to `dracut`(8). This cannot be specified along with `-v`/`--verbose`.
* `-k`, `--hook`: enter "hook mode", which is intended for using the utility in ALPM hooks (see also `alpm-hooks`(5)).
This silences some warnings that might interfere with `pacman`(8)'s operations, and also implies `-y`.
* `--key` *key_file*: Machine Owner Key (MOK) file used to sign kernel image for Secure Boot. If this option is given, then `--cert`
must also be given.
* `--cert` *cert_file*: Machine Owner Key (MOK) certificate file used to sign kernel image for Secure Boot. If this option is given, then `--key`
must also be given.
* `--no-colors`: do not use colors in output. Useful if your terminal does not support colors.
* `--build-fallback`: build fallback initramfs images.
* `--no-fallback`: do not build fallback initramfs images. This takes precedence over `--build-fallback`.
* `-h`, `--help`: print help message.

## CONFIGURATION

In lieu of supplying command-line options, one may configure the program using a persistent configuration.
The configuration for this program is located at `/etc/rebuild-initramfs.yaml`; it must be formatted as a YAML file. The following
keys are supported:

* `key_path`: path to the MOK file used to sign kernel image for Secure Boot. This is equivalent to supplying `--key` on the command line, and will be
overridden by a value provided via command-line flags.
* `cert_path`: path to the MOK certificate used to sign kernel image for Secure Boot. This is equivalent to supplying `--cert` on the command line, and will be
overridden by a value provided via command-line flags.
* `verbose` (boolean): run `rebuild-initramfs` in verbose mode. This is equivalent to supplying `-v`/`--verbose` on the command line, and will be ignored
if `-q`/`--quiet` is supplied on the command line.
* `build_fallback` (boolean): if true, fallback initramfs image will be built. This will be ignored if `--no-fallback` is supplied on the command line.

## SEE ALSO

You might also want to refer to `dracut`(8).

## BUGS

If you find any bugs in the software, please report it at: https://github.com/xuanruiqi/rebuild-initramfs-dracut-arch/issues.

## AUTHOR

Xuanrui Qi (me@xuanruiqi.com)

## LICENSE & COPYRIGHT

The software is licensed for public use and reproduction under the terms of the MIT License. The author owns the copyright 
to and reserves all rights.