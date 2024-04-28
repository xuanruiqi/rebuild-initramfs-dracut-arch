# rebuild-initramfs

A helper script for Arch Linux; rebuild initramfs images using dracut. This is the equivalent of `mkinitcpio -p` and `mkinitcpio -P` for dracut.
It could automatically detect installed kernels and rebuild the initramfs images, or detect and rebuild an initramfs image given an Arch package name.

## Building

You should not be building the project yourself. Rather, you should be using the [AUR package](https://aur.archlinux.org/packages/rebuild-initramfs-dracut)
which I have created.

If you are developing and testing, build it as you would any standard Python project.

## Usage

See the [man page](man.md).

## License

MIT License

## Copyright

Xuanrui Qi (me@xuanruiqi.com), 2024.
