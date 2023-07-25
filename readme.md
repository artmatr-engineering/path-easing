This package allows you to ease the motions of a gcode file.

Keep in mind that it only works with files that have the following structure:
It is important to keep XY moves and Z moves on seperate lines (this is sometimes called 2.5D movement)

- Move to a clearence Z height
- Move to an XY location above the start of a path to be eased
- Move down to the start of the path (at Z=0)
- Move along the path with a series of G1 XY moves
- Move back up to the clearence Z height

An example:

```
G0 Z10 ; Move to the clearence height
G0 X20 Y20 ; Move above the start of a path to be drawn
G0 Z0 ; Move down to start drawing the path
G1 X10 ; Begin drawing a shape
G1 Y10
G1 X0
G1 Y0 ; Finish drawing a shape
G0 Z10 ; Move to the clearence height
```

This format provides a clear difference for the script to be able to determine what is a drawing move and what is a travel move.
