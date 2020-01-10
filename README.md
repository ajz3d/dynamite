# Dynamite Tool for Houdini
## Description
Dynamite is a Python script for Houdini that fits well in the iterative 3D asset development environment, where changes to low and high poly geometry are introduced on a frequent basis.

The script streamlines the process of creating bake cages and reduces tediousness of recreating them whenever the model is replaced by its newer version. With Dynamite you won't need to redo cages of objects which weren't modified in the last iteration, and only those that were altered will require your attention. This reduces the time that would otherwise be spent on redoing all cages from scratch on each consecutive asset iteration.

## Installation
1.  Clone the repository into your `$HOUDINI_USER_PREF_DIR`.
2.  Edit your houdini.env file and add path to extracted folder to `$HOUDINI_PATH` environment variable, for example:
    ```
    # On GNU/Linux:
    HOUDINI_PATH="$HOUDINI_USER_PREF_DIR:$HOUDINI_USER_PREF_DIR/dynamite:&"
    # On Windows:
    HOUDINI_PATH="C:\Users\YourName\Documents\dynamite;&"
    ```
3.  Start Houdini.
4.  Add `Dynamite` shelf to your shelf bar.
5.  Click the `Dynamite` shelf tool to create the control node.

## How to Use?
### Requirements
Your retopo and reference meshes must have corresponding object names. What it means is that if you have, for instance, a character wearing a suit and a tie in your sculpture, and you retopologize those two high resolution objects into one object named `body`, then you also need to combine `suit` and `tie` objects in your sculpture into one named `body`. It also means that the number of reference objects must be the same as the number of retopo objects.

If object names do not correspond to each other, Dynamite will not work (it will notify you about the problem).

Probably the best way of verifying that reference and retopo meshes correspond to each other is to import both of them into a single geometry object node and compare their primitive groups. First check if the quantity of primitive groups in both inputs match, then sort and compare their primitive group names.

### Preparing The Import
Click the **Dynamite** tool. This will create a new *Dynamite* control node that manages most functions of the tool.

In the *Import* tab, select the retopo and reference paths. You can use `op:/` as long as you enclose the path in back-ticks. Use of `op:/` is recommended. Houdini's `.geo` (and derivatives), Wavefront `.obj` and FilmBox `.fbx` are currently the only officially supported input file formats. Other formats are untested, so use them at your own risk.

If the imported object is too small for your current viewport, you can tweak the `Import Scale` parameter at any time. However keep in mind that this parameter is applied in pre-process. Any modifications to cages will be affected by it, so it's best to determine the proper scale before you start to modify them.

`Smooth Normals` parameter will smooth out reference normals.

Click the `Create Network` button on the `Import` tab to generate *retopo-reference-cage groups* for each object. We're going to call those *retopo-reference-cage* triplets **bake bundles** or **bake groups** from now on.

> ***TIP:***
> *As Dynamite input source, I highly recommend to take advantage of `op:/` pointing at some geometry operators. I find it much faster to prepare retopo and reference primitive groups for baking directly in Houdini, than in other DCC programs.*

### Editing Cages
After bake bundles are created, go to the `Edit` tab. Here you will find all objects that you have defined in your model. Each of them will have several parameters available for tweaking.
-   **Isolate**: This button is most probably the first so-called *red* button your fingers should feel itchy to press. What it does is it isolates reference and cage meshes of the current object from the others, so that you can not only focus on tweaking a cage for the current object, but you also gain some performance boost that would otherwise be lost by the presence of other high-poly geometry in the viewport.
-   **Translate**: Translates the whole bundle in a specific direction. This is useful if you intend to bake your model in a software that does not support name correspondence baking, like *xNormal*. You can ignore this parameter if you're baking in Substance Painter or Designer.

> ***TIP:***
> *For exploding, I recommend keyframing all bundles at their default positions ``(0,0,0)`` at frame 0, then translating them as you will and keyframing at frame 1. This way you will be able to quickly switch between "exploded" and "non-exploded" version of your model in no time.*

-   **Peak Distance**: This is the first parameter you will want to tweak. It inflates the cage along its point (or vertex) normals.

> ***TIP:***
> *In order to spot interpenetrations better while you're tweaking cages, you might want to temporarily disable viewport lighting.*

-   **Edit Cage**: If you realize that the distance between inflated cage and the reference mesh gets too large, but is still insufficient to cover all intersections, you might want to consider making local changes to the cage mesh. When you press this button, you will be taken to an *Edit SOP* inside the cage object node of the current bake bundle. When you're in there, switch to translate handle and move intersecting cage primitives (or other components) on positive Z-axis until until the intersection with reference geometry disappears.
In the cage object node you will also find two green `null` SOPs called **USER_BEGIN** and **USER_END**. You can insert any topology-independent geometry deformers between them, like muscle deformer for example.
After you are done tweaking, press the *back* arrow to return to control node.
-   **Show Retopo/Reference/Cage**: These check boxes change visibility of corresponding bake bundle meshes.
-   **Reset Changes**: Resets the current cage object to default, destroying all changes that you have done to it. It will also move the whole bundle back to its origin.
-   **Show Reference and Cages** and **Show Cages Only**: These buttons will display either reference and cage meshes of all bake bundles, or only their cages. The first is useful for a final inspection of your model in order to check if there are no reference/cage surface interpenetrations. The second button will probably be removed.

### Exporting
After tweaking all of your cages you jump to `Export` tab.
Here you can define export paths of your model. I strongly recommend to use the same file format for all of the output paths, preferably an FBX.

You can choose which FBX version to use for export and to export it in ASCII or binary formats.

**Export Scale**: Allows for tweaking the scale of the exported object. Use it only if you experience loss of precision during baking or to compensate for import scale.

**Use Name Correspondence**: By enabling this toggle you will tell Dynamite to add suffixes to object names of retopo and reference meshes. Suffixes can be defined in **Retopo Suffix** and **Reference Suffix** parameters. If retopo suffix is set to `low` and reference suffix is set to `high`, object named `body` will be exported as `body_low` and `body_high`. This is useful for baking in Substance Painter. Note that if you're baking in *xNormal*, you will have to explode your bake groups instead of using name correspondence baking.

**Triangulate** - triangulates the retopo mesh. Cage mesh will pick the triangulation up from retopo mesh. This is disabled by default because triangulation clutters the viewport and makes tweaking the cage more difficult. For a proper bake, make sure you enable it before exporting your bake bundles and make sure the triangulation matches your final asset's. Triangulation is performed with the *Divide SOP* set to defaults. Its settings will be externalized in the next version. Delaunay triangulation would be very welcome as an option if someone could provide its implementation... ;)

**NOTE:** If you're exporting to FBX files, display flag of the subnet containing Dynamite network must be enabled (ROPs must be able to see what they are exporting). Otherwise, exported FBX files will be empty and unreadable.

Press **Export All** button to export all bake groups. Load the result in the baker of your choice.

### Assets for Offline Rendering
If your model is going to be subdivided, either manually before the render or during the render-time, then consider enabling `SubDiv Geometry` parameter and choose the matching global subdivision algorithm.

Each bake bundle gets its own `iterations` parameter on the `Edit` tab. *Iterations* initially was a global parameter, however I noticed that some of the bake groups might need to be subdivided more or less than the others, depending on their polycount and size.

Appliance of appropriate subdivision to bake bundles will ensure that their UVs, and baked textures as a result, will more-or-less match those of your rendered asset.

If you need to take advantage of subdivision creases, press the **Edit Cage** button and put *Crease SOPs* between green **USER_BEGIN** and **USER_END** nulls.

### Updating The Network
If you introduced some changes to your model, you will have to click the **Import⟶Update Network** button. Dynamite will reload your input files, check if any new objects have been added or removed, and modify the network accordingly.

Cages of objects with altered point order will need to be inspected. If you have used peak or muscle deformer, then you probably won't have to edit cages of modified objects unless you introduced some large scale deformations that moved points away from the muscle deformer's range. If you have edited the cage via **Edit⟶Edit Cage** then you will have to reset this node either by clicking the **Reset All Changes** button on the node itself, or by pressing the **Reset Changes** in the **Edit** tab of the *Dynamite Control Node* and then redo the cage for that object.

Cages of objects with unchanged point order do not need to be inspected and modified.

## License
See the [LICENSE](https://github.com/ajz3d/dynamite/blob/master/LICENSE) file.
