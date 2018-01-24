# Dynamite Tool for Houdini
## Description
Dynamite is a Python script for Houdini that fits perfectly for the iterative 3D asset development environment, where changes to low and high poly geometry are introduced on frequent basis.

The script streamlines the process of creating cages and reduces tediousness of recreating them whenever the model is replace by its new version. With Dynamite you won't need to redo cages of objects which weren't modified in the last iteration, and only those that were altered will require your attention. This cuts the wasted time that would otherwise be spent on redoing all cages from scratch on each consecutive asset iteration.

## Installation
1.  Clone or download Dynamite repository and extract `./python2.7libs` to your `HOUDINI_USER_PREF_DIR`. Usually it's `c:\Users\your_user_name\Documents\Houdinixx.x` on Windows.
2.  Extract contents of `./tool` to `HOUDINI_USER_PREF_DIR\tool` directory.
3.  Start Houdini.
4.  Add `Dynamite` shelf to your shelf bar.
5.  Click the `Dynamite` shelf tool.

If you don't want to clutter your shelf bar with yet another shelf, you can create a new shelf tool wherever you like and paste the following code into its **Script** section:

```python
import dynamite.dynamite as dynamite
reload(dynamite)

def getCurrentNetworkEditor(desktop):
    for pane in desktop.paneTabs():
        if isinstance(pane, hou.NetworkEditor) and pane.isCurrentTab():
            return pane

if hou.node('/obj/dynamite_control') is not None:
    control_node = hou.node('/obj/dynamite_control')
    getCurrentNetworkEditor(hou.ui.curDesktop()).setCurrentNode(control_node)
else:
    control_node = dynamite.create_control_node()
    getCurrentNetworkEditor(hou.ui.curDesktop()).setCurrentNode(hou.node('/obj/dynamite_control'))
```
Do note however, that you will need to update this code every time you install a newer version of Dynamite because there's always a chance that some changes might be introduced to shelf tool.

## Usage
### Requirements
Your retopo and reference meshes must have corresponding object names. What it means is that if you have, for instance, a character wearing a suit and a tie in your sculpture, and you retopologize those two high resolution objects into one object named `body`, then you also need to combine `suit` and `tie` objects in your sculpture into one named `body`. It also means that the number of reference objects must be the same as the number of retopo objects.

If object names do not correspond to each other, Dynamite will not work (it will notify you about the problem).

Probably the best way of verifying that reference and retopo meshes correspond to each other is to import both of them into a single geometry object node and compare their primitive groups. First check if the quantity of primitive groups in both inputs match, then sort and compare their primitive group names.

### Preparing The import
Click the **Dynamite** tool. This will create a new *Dynamite* control node that manages most functions of the tool.

In the *Import* tab, select the retopo and reference paths. You can use `op:/` as long as you enclose the path in backticks. Use of `op:/` is recommended. Houdini's `.geo` (and derivatves), Wavefront `.obj` and FilmBox `.fbx` are currently the only officialy supported input file formats. Other formats are untested, so use them at your own risk.

If the imported object is too small for your current viewport, you can tweak the `Import Scale` parameter at any time. However keep in mind that this parameter is applied in preprocess. Any modifications to cages will be affected by it, so it's best to determine the proper scale before you start to modify them.

`Smooth Normals` parameter will smooth out retopo and reference normals. This parameter is **DEPRECATED** and will most likely be removed from future Dynamite versions in favor of smoothing reference normals only, so I suggest to smooth your reference mesh and apply appropriate retopo normals before importing your files to Houdini. Or do it in Houdini and link the output with **op:/** (recommended).

Click the `Create Network` button on the `Import` tab to generate *retopo-reference-cage groups* for each object. We're going to call those *retopo-reference-cage* triplets **bake bundles** or **bake groups** from now on.

### Editing Cages
After bake bundles are created, go to the `Edit` tab. Here you will find all objects that you have defined in your model. Each of them will have several parameters available for tweaking.
-   **Isolate**: This button is most probably the first so-called *red* button your fingers should feel itchy to press. What it does is it isolates reference and cage meshes of the current object from the others, so that you can not only focus on tweaking a cage for the current object, but you also gain some performance boost that would otherwise be lost by the presence of other high-poly geometry in the viewport.
-   **Translate**: Translates the whole bundle in a specific direction. This is useful if you intend to bake your model in a software that does not support name correspondence baking, like *xNormal*. You can ignore this parameter if you're baking in Substance Painter or Designer.

> ***TIP***
> *For exploding, I recommend keyframing all bundles at their default positions ``(0,0,0)`` at frame 0, then translating them as you will and keyframing at frame 1. This way you will be able to quickly switch between "exploded" and "non-exploded" version of your model in no time.*

-   **Peak Distance**: This is the first parameter you will want to tweak. It inflates the cage along its point (or vertex) normals.

> ***TIP:***
> *In order to spot interpenetrations better while you're tweaking cages, you might want to temporarily disable viewport lighting.*

-   **Edit Cage**: If you realize that the distance between inflated cage and the reference mesh gets too large, but is still insufficient to cover all intersections, you might want to consider making local changes to the cage mesh. When you press this button, you will be taken to an *Edit SOP* inside the cage object node of the current bake bundle. When you're in there, switch to translate handle and move intersecting cage primitives (or other components) on positive Z-axis until untill the intersection with reference geometry disappears.
In the cage object node you will also find two green `null` SOPs called **USER_BEGIN** and **USER_END**. You can insert any topology-independent geometry deformers between them, like muscle deformer for example.
After you are done tweaking, press the *back* arrow to return to control node.
-   **Show Retopo/Reference/Cage**: These check boxes change visibility of corresponding bake bundle meshes.
-   **Reset Changes**: Resets the current cage object to default, destroying all changes that you have done to it. It will also move the whole bundle back to its origin.
-   **Show Reference and Cages** and **Show Cages Only**: These buttons will display either reference and cage meshes of all bake bundles, or only their cages. The first is useful for a final inspection of your model in order to check if there are no reference/cage surface interpenetrations. The second button will probably be removed.

### Exporting
After tweaking all of your cages you jump to `Export` tab.
Here you can define export paths of your model. I strongly recommend to use the same file format for all of the output paths, preferably an FBX.

You can choose which FBX version to use for export and to export it in ASCII or binary formats. Please note that ASCII FBX reference file will take a very long time to load in some software, like Substance Painter for example (load time will be longer than Wavefront OBJ), so binary format is recommended if you choose to use FilmBox.

**Export Scale**: Allows for tweaking the scale of the exported object. Use it only if you experience loss of precision during baking or to compensate for import scale.

**Use Name Correspondence**: By enabling this toggle you will tell Dynamite to add suffixes to object names of retopo and reference meshes. Suffixes can be defined in **Retopo Suffix** and **Reference Suffix** parameters. If retopo suffix is set to `low` and reference suffix is set to `high`, object named `body` will be exported as `body_low` and `body_high`. This is useful for baking in Substance Painter. Note that if you're baking in *xNormal*, you will have to explode your bake groups instead of using name correspondence baking.

**Triangulate** - triangulates the retopo mesh. Cage mesh will pick the triangulation up from retopo mesh. This is disabled by default because triangulation clutters the viewport and makes tweaking the cage more difficult. For a proper bake, make sure you enable it before exporting your bake bundles and make sure the triangulation matches your final asset's. Triangulation is peformed with the *Divide SOP* set to defaults. Its settings will be externalized in the next version. Delaunay triangulation would be very welcome as an option if someone could provide its implementation... ;)

Press **Export All** button to export all bake groups. Load the result in the baker of your choice.

### Offline Rendering
If your model is going to be subdivided, either manually before the render or during the render-time, then consider enabling `SubDiv Geometry` parameter and choose the matching global subdivision algorithm.

Each bake bundle gets its own `iterations` parameter on the `Edit` tab. *Iterations* initially was a global parameter, however I noticed that some of the bake groups might need to be subdivided more or less than the others, depending on their polycount and size.

Appliance of appropriate subdivision to bake bundles will ensure that their UVs, and baked textures as a result, will more-or-less match those of your rendered asset.

If you need to take advantage of subdivision creases, press the **Edit Cage** button and put *Crease SOPs* between green **USER_BEGIN** and **USER_END** nulls.

### Updating The network
#### After Minor Changes
If you introduced some changes to your model which do not result in objects being deleted, or new objects groups being added, you won't have to update your network. All you'll have to do is to go through each modified object/primitive group that you have changed (by isolating them) and see if the changes you made didn't introduce some reference-cage interpenetrations or resulted in a mangled cage (remember that Edit SOP depends on topology) If you didn't manually edit the cage and the changes weren't drastic, you should be okay. Otherwise, you should probably either alter the peak distance, slightly tweak the cage, or in the worst case - reset the cage of the object.
#### After Major Changes
If you removed some objects, added some new renamed existing ones, you will have to update the whole network by pressing the **Update Network** button on the **Import** tab.

It will delete all bake bundles that were not found in the new version of the asset, and create new ones if they didn't exist before.

Or it will notify you that retopo and reference object names do not correspond to each other.

## License
See the LICENSE.md file.
