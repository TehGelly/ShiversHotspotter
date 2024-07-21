# ShiversHotspotter
Program to modify Shivers resources in-place to add hotspot information

Uses scripts from https://github.com/sluicebox/sci-scripts/tree/main for parsing purposes (goes to shivers-win-1.02). It is possible to parse the information from scripts gathered from the RESSCI file itself, but since such good work was put into the sci-script decompilation, I figured it would only be best to use that information instead of fighting against SCI scripts myself.

Uses https://github.com/cmcqueen/lzs-compression for compression better, usually, than the game compression had. Without it, a lot of shuffling would have to be made. There's still quite a few instances where adding the hotspots will induce a compression cost, but the hacky way is to either ignore those entrries or black out the edges of the image to decrease unnecessary information.

To use for yourself, the script will read all the scripts in *shivers-win-1.02*, pull all the available p56 pictures referenced from *p56s* (pre-extracted using sierra viewer CLI), draw all found hotspots, place into *processed_p56s*, then attempt to compress all found processed files using lzs-compress and place them in the RESSCI.000 file in the directory, with help from RESMAP.000.

TODO:
-Outline all views that have doVerb information in scripts, as that indicates having hotspots. Most views have cel information that complicates the simple current image modification method.
-make this vaguely of professional construction