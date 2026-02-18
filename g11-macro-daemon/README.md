# g11-macro-daemon
Application that provides Linux support for the macro keys of a Logitech G11 keyboard.

The regular keys (and media keys) of the G11 keyboard operate on a separate interface.
They already work fine in Linux and are not of interest here.

## Features/Behaviour
* Runs in the background as a Linux service
* Reads macro definitions from a user-owned config file
* When a 'G' key is pressed, will execute the associated macro (if configured)
* Supports banking with the 'M' keys, with LED feedback
* The 'MR' key can be used for recording macros on the fly

### GUI
A graphical configuration tool is available in [`../gui/`](../gui) — see the [project README](../README.md) for setup instructions.

### G15 Support
Allegedly, the Logitech G15 keyboard uses the same interface as the G11 for its macro keys.
So this application might work for that too, but I have no way of testing this. Worth a shot if you have one.

## Installation/Configuration
* See [INSTALLATION.md](INSTALLATION.md)
* See [CONFIGURATION.md](CONFIGURATION.md)

## Key Layout
The macro keys interface covers:
* 18 programmable 'G' keys
* 3 'M' keys that operate as banks for the 'G' keys (allowing for 54 total macros) - _each has its own LED_
* 1 'MR' key that allows macros to be recorded on the fly - _has its own LED_
* 1 Backlight key that has nothing to do with macros but runs on the same interface
```text
  (M1) (M2) (M3)  (MR)   ...   (💡)

 ┌───┐┌───┐┌───┐
 │G1 ││G2 ││G3 │
 └───┘└───┘└───┘
 ┌───┐┌───┐┌───┐
 │G4 ││G5 ││G6 │
 └───┘└───┘└───┘

 ┌───┐┌───┐┌───┐
 │G7 ││G8 ││G9 │
 └───┘└───┘└───┘
 ┌───┐┌───┐┌───┐
 │G10││G11││G12│
 └───┘└───┘└───┘

 ┌───┐┌───┐┌───┐
 │G13││G14││G15│
 └───┘└───┘└───┘
 ┌───┐┌───┐┌───┐
 │G16││G17││G18│
 └───┘└───┘└───┘
```
