# -*- coding: utf-8 -*-

# ===== dynamite.py
#
# Copyright (c) 2016-2018 Artur J. Żarek
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Main module of the Dynamite tool for Houdini. It allows for preparing low-poly and high-poly geometry
for texture baking by exploding the geometry and creating bake cages.
"""
import hou
import topo_match
import os
import sys
import time
import toolutils

__version__ = '0.9.2'


class Dynamite(object):
    """Abstract class containing script-specific enumerations."""
    def __init__(self): raise AttributeError, "Can't instantiate an abstract class."
    MODULE_IMPORT = 'import dynamite.dynamite as dynamite'
    RETOPO_OUTPUT_OBJ_NAME = 'retopo_output'
    REFERENCE_OUTPUT_OBJ_NAME = 'reference_output'
    CAGE_OUTPUT_OBJ_NAME = 'cage_output'
    RETOPO_GROUP = 'retopo'
    REFERENCE_GROUP = 'reference'
    CAGE_GROUP = 'cage'


class DynamiteColor(object):
    """Abstract class containing color presets."""
    def __init__(self): raise AttributeError, "Can't instantiate an abstract class."
    BLACK = hou.Color((0, 0, 0))
    GOLD = hou.Color((0.8, 0.6, 0.0))
    GRAY = hou.Color((0.25, 0.25, 0.25))
    GRAY_DARK = hou.Color((0.15, 0.15, 0.15))
    GRAY_LIGHT = hou.Color((0.35, 0.35, 0.35))
    GREEN = hou.Color((0, 0.35, 0))
    RED_DARK = hou.Color((0.25, 0, 0))
    RED = hou.Color((0.50, 0, 0))


def create_control_node(path='/obj', in_retopo='$HIP/geo_bake/in_retopo.bgeo',
                        in_reference='$HIP/geo_bake/in_reference.bgeo',
                        out_retopo='$HIP/geo_bake/out_retopo.fbx',
                        out_reference='$HIP/geo_bake/out_reference.fbx',
                        out_cage='$HIP/geo_bake/out_cages.fbx'):
    """Routine for creating the main Dynamite control node, in the path provided as string.
    Arguments:
        path - path where the control node will be generated (untested!).
        in_retopo - default path to retopo source file. "op:/..." path type should be surrounded with "`" chars.
        in_reference - default path to reference source file. "op:/..." path type should be surrounded with "`" chars.
        out_retopo - default retopo export path.
        out_reference - default reference export path.
        out_cage - default cage export path.
    :type path: str
    :type in_retopo: str
    :type in_reference: str
    :type out_retopo: str
    :type out_reference: str
    :type out_cage: str
    """
    control_node = hou.node(path).createNode('null')
    control_node.setName('dynamite_control')
    control_node.setDisplayFlag(False)
    control_node.setSelectableInViewport(False)
    control_node.setColor(DynamiteColor.RED_DARK)
    set_node_shape(control_node, 23)
    # control_node.setUserData('nodeshape', hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor).nodeShapes()[23])
    control_node.moveToGoodPosition()
    destroy_children(control_node)

    # Create parmTemplateGroup.
    parm_template_group = control_node.parmTemplateGroup()
    parm_template_group.hideFolder('Transform', True)
    parm_template_group.hideFolder('Render', True)
    parm_template_group.hideFolder('Misc', True)
    control_node.setParmTemplateGroup(parm_template_group)

    # Create parameters for import tab.
    help = "Subdivides the retopo and cage meshes."
    subdivide = hou.ToggleParmTemplate('subdivide', 'SubDiv Geometry', False, help=help)

    menu_labels = ('Houdini Catmull-Clark', 'Mantra-Compatible Catmull-Clark', 'OpenSubdiv Catmull-Clark',
                   'OpenSubdiv Loop', 'OpenSubdiv Bilinear')
    disable_when = '{ subdivide == 0 }'
    help = "Choose the algorithm used to perform subdivision."
    subdivision_algorithm = hou.MenuParmTemplate(
        'algorithm', 'Algorithm', ("0", "1", "2", "3", "4"),
        menu_labels=menu_labels, default_value=2, disable_when=disable_when, help=help)

    help = "Path to retopo file.%sIf you want to use 'op:/', enclose everything in backticks." % (os.linesep,)
    retopo_source_path = hou.StringParmTemplate('retopo_source_path', 'Retopo Path', 1,
                                                naming_scheme=hou.parmNamingScheme.Base1,
                                                string_type=hou.stringParmType.FileReference,
                                                default_value=(in_retopo,), help=help)

    # script_callback = "hou.node('%s/retopo_source/retopo_source_file').cook()" % path
    # disable_when = '{ network_exists == 0 }'
    # reload_retopo_button = hou.ButtonParmTemplate('reload_retopo_source', 'Reload',
    #                                               disable_when=disable_when, script_callback=script_callback,
    #                                               script_callback_language=hou.scriptLanguage.Python)

    help = "Path to reference file.%sIf you want to use 'op:/', enclose everything in backticks." % (os.linesep,)
    reference_source_path = hou.StringParmTemplate('reference_source_path', 'Reference Path', 1,
                                                   naming_scheme=hou.parmNamingScheme.Base1,
                                                   string_type=hou.stringParmType.FileReference,
                                                   default_value=(in_reference,), help=help)

    # script_callback = "hou.node('%s/reference_source/reference_source_file').cook()" % path
    # disable_when = '{ network_exists == 0 }'
    # reload_reference_button = hou.ButtonParmTemplate('reload_reference_source', 'Reload',
    #                                                  disable_when=disable_when, script_callback=script_callback,
    #                                                  script_callback_language=hou.scriptLanguage.Python)

    help = "Scale modifier of the imported object.%s" \
        "Modify if original object scale makes it too incomfortable to work with in Houdini." % (os.linesep,)
    import_scale = hou.FloatParmTemplate('import_scale', 'Import Scale', 1, default_value=(1.0,), help=help)

    help = "Smooth reference normals."
    smooth_normals = hou.ToggleParmTemplate('smooth_normals', 'Smooth Normals', True, help=help)

    script_callback = '%s;dynamite.create_network(hou.pwd())' % Dynamite.MODULE_IMPORT
    help = "Creates bake groups for each retopo object/primitive group."
    disable_when = '{ network_exists == 1 }'
    create_network_button = hou.ButtonParmTemplate('create_network', 'Create Network',
                                                   script_callback=script_callback,
                                                   script_callback_language=hou.scriptLanguage.Python,
                                                   disable_when=disable_when, join_with_next=True, help=help)

    script_callback = '%s;dynamite.update_network(hou.pwd())' % Dynamite.MODULE_IMPORT
    help = "Updates the network. Required on each asset iteration."
    disable_when = '{ network_exists == 0 }'
    update_network_button = hou.ButtonParmTemplate('update_network', 'Update Network',
                                                   script_callback=script_callback,
                                                   script_callback_language=hou.scriptLanguage.Python,
                                                   disable_when=disable_when, help=help)

    # Create parameters for export tab.
    help = "Path to output retopo file."
    retopo_export_path = hou.StringParmTemplate('retopo_export_path', 'Retopo Export Path', 1,
                                                string_type=hou.stringParmType.FileReference,
                                                default_value=(out_retopo,), help=help)

    help = "Path to output reference file."
    reference_export_path = hou.StringParmTemplate('reference_export_path', 'Reference Export Path', 1,
                                                   string_type=hou.stringParmType.FileReference,
                                                   default_value=(out_reference,), help=help)

    help = "Path to output cage file."
    cage_export_path = hou.StringParmTemplate('cage_export_path', 'Cage Export Path', 1,
                                              string_type=hou.stringParmType.FileReference,
                                              default_value=(out_cage,), help=help)

    help = "If you choose a FilmBox file as your output format, this is the FBX version the file will use."
    menu_items = ('FBX | FBX201600', 'FBX | FBX201400', 'FBX | FBX201300', 'FBX | FBX201200', 'FBX | FBX201100',
                  'FBX 6.0 | FBX201000', 'FBX 6.0 | FBX200900', 'FBX 6.0 | FBX200611')
    fbx_sdk_version = hou.MenuParmTemplate('sdk_version', 'FBX SDK Version',
                                           menu_items=menu_items, menu_labels=menu_items, help=help)

    help = "Should the FBX be exported in ASCII format?"
    fbx_ascii = hou.ToggleParmTemplate('fbx_ascii', 'FBX ASCII Export', default_value=False, help=help)

    help = "Output will be scaled by this factor. Use if you encounter some bake artifacts because of object scale."
    export_scale = hou.FloatParmTemplate('export_scale', 'Export Scale', 1, default_value=(1.0,), help=help)

    help = "Adds suffixes to retopo and reference output."
    use_name_correspondence = hou.ToggleParmTemplate('name_correspondence', 'Use Name Correspondence',
                                                     default_value=True, help=help)

    help = "Suffix to add to retopo objects if 'Use name correspondence' is enabled."
    disable_when = '{ name_correspondence == 0 }'
    retopo_suffix = hou.StringParmTemplate('retopo_suffix', 'Retopo Suffix', 1,
                                           string_type=hou.stringParmType.Regular, disable_when=disable_when,
                                           default_value=('_low',), help=help)

    help = "Suffix to add to reference objects if 'Use name correspondence' is enabled."
    disable_when = '{ name_correspondence == 0 }'
    reference_suffix = hou.StringParmTemplate('reference_suffix', 'Reference Suffix', 1,
                                              string_type=hou.stringParmType.Regular, disable_when=disable_when,
                                              default_value=('_high',), help=help)

    help = "Triangulates retopo and cage outputs."
    triangulate = hou.ToggleParmTemplate('triangulate', 'Triangulate', False, help=help)

    help = "Export retopo and cage objects."
    script_callback = "%s;dynamite.export(True, False, True, hou.node('%s'))" % (
        Dynamite.MODULE_IMPORT, control_node.path())
    disable_when = '{ network_exists == 0 }'
    export_retopo_cage_button = hou.ButtonParmTemplate('export_retopo_cage', 'Export Retopo and Cage',
                                                       disable_when=disable_when, script_callback=script_callback,
                                                       script_callback_language=hou.scriptLanguage.Python,
                                                       join_with_next=True, help=help)

    help = "Export reference objects."
    script_callback = "%s;dynamite.export(False, True, False, hou.node('%s'))" % (
        Dynamite.MODULE_IMPORT, control_node.path())
    disable_when = '{ network_exists == 0 }'
    export_reference_button = hou.ButtonParmTemplate('export_reference', 'Export Reference',
                                                     disable_when=disable_when, script_callback=script_callback,
                                                     script_callback_language=hou.scriptLanguage.Python, help=help)

    help = "Export all bake groups."
    script_callback = "%s;dynamite.export(True, True, True, hou.node('%s'))" % (
        Dynamite.MODULE_IMPORT, control_node.path())
    disable_when = '{ network_exists == 0 }'
    export_button = hou.ButtonParmTemplate('export', 'Export All', disable_when=disable_when,
                                           script_callback=script_callback,
                                           script_callback_language=hou.scriptLanguage.Python, join_with_next=True,
                                           help=help)

    # Create parameters for data tab.
    network_exists = hou.ToggleParmTemplate('network_exists', 'Network Exists', False)

    network_location = hou.StringParmTemplate('network_location', 'Network Location', 1,
                                              string_type=hou.stringParmType.NodeReference)

    retopo_source = hou.StringParmTemplate('retopo_source', 'Retopo Source Object', 1,
                                           string_type=hou.stringParmType.NodeReference)

    reference_source = hou.StringParmTemplate('reference_source', 'Reference Source Object', 1,
                                              string_type=hou.stringParmType.NodeReference)

    retopo_source_file_sop = hou.StringParmTemplate('retopo_source_file_sop', 'Retopo Source File SOP', 1,
                                                    string_type=hou.stringParmType.NodeReference)

    retopo_source_temp_file_sop = hou.StringParmTemplate('retopo_source_temp_file_sop', 'Retopo Temp File SOP', 1,
                                                         string_type=hou.stringParmType.NodeReference)

    reference_source_file_sop = hou.StringParmTemplate('reference_source_file_sop', 'Reference Source File SOP', 1,
                                                       string_type=hou.stringParmType.NodeReference)

    reference_source_temp_file_sop = hou.StringParmTemplate('reference_source_temp_file_sop',
                                                            'Reference Temp File SOP', 1,
                                                            string_type=hou.stringParmType.NodeReference)

    retopo_source_fbx = hou.StringParmTemplate('retopo_source_is_fbx',
                                               'Retopo Source FBX Node', 1,
                                               string_type=hou.stringParmType.NodeReference)

    reference_source_fbx = hou.StringParmTemplate('reference_source_is_fbx',
                                                  'Reference Source FBX Node', 1,
                                                  string_type=hou.stringParmType.NodeReference)

    retopo_source_out = hou.StringParmTemplate('retopo_source_out', 'Retopo Source OUT', 1,
                                               string_type=hou.stringParmType.NodeReference)

    reference_source_out = hou.StringParmTemplate('reference_source_out', 'Reference Source OUT', 1,
                                                  string_type=hou.stringParmType.NodeReference)

    retopo_output = hou.StringParmTemplate('retopo_output_obj', 'Retopo Output ObjNode', 1,
                                           string_type=hou.stringParmType.NodeReference)

    reference_output = hou.StringParmTemplate('reference_output_obj', 'Reference Output ObjNode', 1,
                                              string_type=hou.stringParmType.NodeReference)

    cage_output = hou.StringParmTemplate('cage_output_obj', 'Cage Output ObjNode', 1,
                                         string_type=hou.stringParmType.NodeReference)

    retopo_material = hou.StringParmTemplate('retopo_material', 'Retopo Material', 1,
                                             string_type=hou.stringParmType.NodeReference)

    reference_material = hou.StringParmTemplate('reference_material', 'Reference Material', 1,
                                                string_type=hou.stringParmType.NodeReference)

    cage_material = hou.StringParmTemplate('cage_material', 'Cage Material', 1,
                                           string_type=hou.stringParmType.NodeReference)

    prim_groups = hou.StringParmTemplate('prim_groups', 'Prim Groups', 1,
                                         string_type=hou.stringParmType.Regular)

    # Create folders and add them to ParmTemplateGroup.
    folder_import = hou.FolderParmTemplate('import_folder', 'Import')
    folder_export = hou.FolderParmTemplate('export_folder', 'Export')
    folder_edit = hou.FolderParmTemplate('edit_folder', 'Edit')
    folder_data = hou.FolderParmTemplate('date_folder', 'Data')
    parm_template_group.addParmTemplate(folder_import)
    parm_template_group.addParmTemplate(folder_export)
    parm_template_group.addParmTemplate(folder_edit)
    parm_template_group.addParmTemplate(folder_data)

    # Add parameter templates to folders.
    parm_template_group = append_to_folder(parm_template_group, 'Import', subdivide, subdivision_algorithm,
                                           retopo_source_path, reference_source_path,
                                           import_scale, smooth_normals,
                                           create_network_button, update_network_button)

    parm_template_group = append_to_folder(parm_template_group, 'Export', retopo_export_path, reference_export_path,
                                           cage_export_path, fbx_sdk_version, fbx_ascii,
                                           hou.SeparatorParmTemplate('ex_sep1'), export_scale,
                                           use_name_correspondence, retopo_suffix, reference_suffix, triangulate,
                                           hou.SeparatorParmTemplate('ex_sep2'),
                                           export_button, export_retopo_cage_button, export_reference_button)

    parm_template_group = append_to_folder(parm_template_group, 'Data', network_exists,
                                           network_location,
                                           hou.SeparatorParmTemplate('da_sep1'),
                                           retopo_source, reference_source,
                                           hou.SeparatorParmTemplate('da_sep2'),
                                           retopo_source_file_sop, retopo_source_temp_file_sop,
                                           reference_source_file_sop, reference_source_temp_file_sop,
                                           retopo_source_fbx, reference_source_fbx,
                                           retopo_source_out, reference_source_out,
                                           hou.SeparatorParmTemplate('da_sep3'),
                                           retopo_output, reference_output, cage_output,
                                           hou.SeparatorParmTemplate('da_sep4'),
                                           retopo_material, reference_material, cage_material,
                                           hou.SeparatorParmTemplate('da_sep5'),
                                           prim_groups)

    parm_template_group.hideFolder('Data', True)
    control_node.setParmTemplateGroup(parm_template_group)

    # Initialize important parameters on the data tab.
    control_node.parm('network_location').set(path)


def create_network(control_node):
    """Initializes network creation."""
    network_location = control_node.parm('network_location').eval()
    # Create materials.
    cage_material = create_material('cage', 'principledshader', (0.2, 0.6, 0.22), 0.6)
    reference_material = create_material('reference', 'principledshader', (0.6, 0.2, 0.2), 0.6)
    control_node.parm('cage_material').set(cage_material.path())
    control_node.parm('reference_material').set(reference_material.path())

    # Ensures that all source files exist.
    if not path_exists(control_node.parm('retopo_source_path').eval()):
        hou.ui.displayMessage("ERROR: Retopo file doesn't exist.")
        sys.exit(1)
    if not path_exists(control_node.parm('reference_source_path').eval()):
        hou.ui.displayMessage("ERROR: Reference file doesn't exist.")
        sys.exit(1)

    operation = hou.InterruptableOperation('Creating Source Network', long_operation_name='Loading Geometry...',
                                           open_interrupt_dialog=True)
    with operation:
        # For operation percentage calculations.
        op_counter = 0

        # Create source networks.
        operation.updateLongProgress(long_op_status='Creating Retopo Source')
        retopo_source_obj = create_source_network('retopo_source', control_node)
        operation.updateLongProgress(long_op_status='Creating Reference Source')
        reference_source_obj = create_source_network('reference_source', control_node,
                                                     reference_material.path(), True)
        hou.node(control_node.parm('network_location').eval()).layoutChildren()

        retopo_geo = hou.node('%s/is_fbx' % control_node.parm('retopo_source').eval()).geometry()
        reference_geo = hou.node('%s/is_fbx' % control_node.parm('reference_source').eval()).geometry()

        if not primitive_groups_match(retopo_geo, reference_geo):
            retopo_source_obj.destroy()
            reference_source_obj.destroy()
            sys.exit(1)

        retopo_geo = hou.node(control_node.parm('retopo_source_out').eval()).geometry()
        reference_geo = hou.node(control_node.parm('reference_source_out').eval()).geometry()

        # Create bake groups for each primitive group.
        sorted_retopo_prim_groups = list(sorted(retopo_geo.primGroups(), key=lambda prim_group: prim_group.name()))
        op_percentage_full = 2 + 3 * len(sorted_retopo_prim_groups)

        for retopo_prim_group in sorted_retopo_prim_groups:
            prim_group_name = retopo_prim_group.name()

            op_percentage = float(op_counter) / float(op_percentage_full)
            operation.updateLongProgress(op_percentage, 'Creating %s_retopo group.' % prim_group_name)
            retopo_group = create_retopo_group(retopo_prim_group, control_node)
            op_counter += 1

            reference_prim_group = reference_geo.findPrimGroup(prim_group_name)
            op_percentage = float(op_counter) / float(op_percentage_full)
            operation.updateLongProgress(op_percentage, 'Creating %s_reference group.' % prim_group_name)
            reference_group = create_reference_group(reference_prim_group, control_node)
            op_counter += 1

            op_percentage = float(op_counter) / float(op_percentage_full)
            operation.updateLongProgress(op_percentage, 'Creating %s_cage group.' % prim_group_name)
            cage_group = create_cage_group(retopo_prim_group, control_node)
            op_counter += 1

            reference_group.setFirstInput(retopo_group)
            cage_group.setFirstInput(reference_group)

        retopo_output = create_output_group(
            Dynamite.RETOPO_OUTPUT_OBJ_NAME, 'retopo', control_node, control_node.parm('retopo_suffix').eval())
        control_node.parm('retopo_output_obj').set(retopo_output.path())
        reference_output = create_output_group(
            Dynamite.REFERENCE_OUTPUT_OBJ_NAME, 'reference', control_node, control_node.parm('reference_suffix').eval())
        control_node.parm('reference_output_obj').set(reference_output.path())
        cage_output = create_output_group(Dynamite.CAGE_OUTPUT_OBJ_NAME, 'cage', control_node)
        control_node.parm('cage_output_obj').set(cage_output.path())

        # Update control node parameters.
        # Add script callback for retopo and reference suffixes.
        retopo_suffix_sop = hou.node('%s/add_suffix' % retopo_output.path())
        reference_suffix_sop = hou.node('%s/add_suffix' % reference_output.path())

        parm_template_group = control_node.parmTemplateGroup()
        retopo_suffix = parm_template_group.find('retopo_suffix')
        reference_suffix = parm_template_group.find('reference_suffix')

        script_callback = "%s;hou.node('%s').parm('newname1').set('*_' + hou.pwd().parm('retopo_suffix').eval())" % (
            Dynamite.MODULE_IMPORT, retopo_suffix_sop.path())
        retopo_suffix.setScriptCallback(script_callback)
        retopo_suffix.setScriptCallbackLanguage(hou.scriptLanguage.Python)

        script_callback = "%s;hou.node('%s').parm('newname1').set('*_' + hou.pwd().parm('reference_suffix').eval())" % (
            Dynamite.MODULE_IMPORT, reference_suffix_sop.path())
        reference_suffix.setScriptCallback(script_callback)
        reference_suffix.setScriptCallbackLanguage(hou.scriptLanguage.Python)

        parm_template_group.replace('retopo_suffix', retopo_suffix)
        parm_template_group.replace('reference_suffix', reference_suffix)
        control_node.setParmTemplateGroup(parm_template_group)

        # Tidy up.
        hou.node(network_location).layoutChildren()
        control_node.parm('network_exists').set(True)
        home_network(network_location)


def create_source_network(node_name, control_node, material='', smooth_normals=False):
    """Creates retopo and reference source networks.
    Arguments:
        node_name - prefix of the network (e.g. retopo, reference)
        control_node - Dynamite control hou.ObjNode.
        material - path to material that the generated network will use.
        smooth_normals - smooth geometry normals.
    :type node_name: str
    :type control_node: hou.ObjNode
    :type material: str
    :type smooth_normals: bool"""
    network_location = control_node.parm('network_location').eval()
    geo_node = hou.node(network_location).createNode('geo')
    geo_node.setName(node_name)
    geo_node.setColor(DynamiteColor.GRAY)
    set_node_shape(geo_node, 7)
    geo_node.setDisplayFlag(False)
    geo_node.setSelectableInViewport(False)
    destroy_children(geo_node)

    file_sop = geo_node.createNode('file')
    file_sop.setName('%s_file' % node_name)
    control_node.parm('%s_file_sop' % node_name).set(file_sop.path())

    # Temp node required for update network.
    file_temp_sop = geo_node.createNode('file')
    file_temp_sop.setName('%s_temp_file' % node_name)
    control_node.parm('%s_temp_file_sop' % node_name).set(file_temp_sop.path())

    vex_snippet = """setprimgroup(0, s@fbx_node_name, @primnum, 1, "set");
    s@shop_materialpath = s@material_name;"""
    fbx_restore_prim_groups = geo_node.createNode('attribwrangle')
    fbx_restore_prim_groups.setName('fbx_restore_prim_groups')
    fbx_restore_prim_groups.parm('class').set(1)
    fbx_restore_prim_groups.parm('snippet').set(vex_snippet)

    fbx_attrib_delete = geo_node.createNode('attribdelete')
    fbx_attrib_delete.setName('fbx_attrib_cleanup')
    fbx_attrib_delete.parm('ptdel').set('fbx_*')
    fbx_attrib_delete.parm('primdel').set('fbx_* material_name')
    fbx_attrib_delete.parm('varmap')

    is_fbx_switch = geo_node.createNode('switch')
    is_fbx_switch.setName('is_fbx')
    if is_path_fbx(control_node.parm('retopo_source_path').eval()):
        is_fbx_switch.parm('input').set(1)
    else:
        is_fbx_switch.parm('input').set(0)

    # Temp nodes required for update network && FBX support. Sucks, I know. :(
    fbx_restore_prim_groups_temp = geo_node.createNode('attribwrangle')
    fbx_restore_prim_groups_temp.setName('fbx_restore_prim_groups_temp')
    fbx_restore_prim_groups_temp.parm('class').set(1)
    fbx_restore_prim_groups_temp.parm('snippet').set(vex_snippet)

    fbx_attrib_delete_temp = geo_node.createNode('attribdelete')
    fbx_attrib_delete_temp.setName('fbx_attrib_cleanup_temp')
    fbx_attrib_delete_temp.parm('ptdel').set('fbx_*')
    fbx_attrib_delete_temp.parm('primdel').set('fbx_* material_name')
    fbx_attrib_delete_temp.parm('varmap')

    is_fbx_switch_temp = geo_node.createNode('switch')
    is_fbx_switch_temp.setName('is_fbx_temp')
    if is_path_fbx(control_node.parm('retopo_source_path').eval()):
        is_fbx_switch_temp.parm('input').set(1)
    else:
        is_fbx_switch_temp.parm('input').set(0)

    out_temp = geo_node.createNode('null')
    out_temp.setName('OUT_TEMP')
    out_temp.setColor(DynamiteColor.BLACK)

    # TODO: It will overwrite the obj-level material assignment.
    # TODO: Candidate for removal.
    material_sop = geo_node.createNode('material')
    material_sop.parm('shop_materialpath1').set(material)
    material_sop.bypass(True)

    normal_sop = geo_node.createNode('normal')
    normal_sop.setName('%s_smooth_normals' % node_name)
    normal_sop.parm('type').set(1)
    normal_sop.parm('cuspangle').set(180)

    normal_switch_sop = geo_node.createNode('switch')
    normal_switch_sop.setName('%s_smooth_normals_switch' % node_name)
    if smooth_normals:
        normal_switch_sop.parm('input').set(control_node.parm('smooth_normals'))
    else:
        normal_switch_sop.parm('input').set(0)

    xform_sop = geo_node.createNode('xform')
    xform_sop.setName('%s_xform' % node_name)
    xform_sop.parm('scale').set(control_node.parm('import_scale'))

    out_sop = geo_node.createNode('null')
    out_sop.setName('OUT')
    out_sop.setDisplayFlag(True)
    out_sop.setRenderFlag(True)
    out_sop.setColor(DynamiteColor.BLACK)

    control_node.parm('%s_out' % node_name).set(out_sop.path())

    group = geo_node.parmTemplateGroup()
    set_default_folders_hidden(group)
    file_sop.parm('file').set(control_node.parm('%s_path' % node_name).eval())

    control_node.parm(node_name).set(geo_node.path())

    # Connections
    fbx_attrib_delete.setInput(0, fbx_restore_prim_groups)
    fbx_restore_prim_groups.setInput(0, file_sop)
    is_fbx_switch.setInput(0, file_sop)
    is_fbx_switch.setInput(1, fbx_attrib_delete)
    normal_sop.setInput(0, is_fbx_switch)
    normal_switch_sop.setInput(0, is_fbx_switch)
    normal_switch_sop.setInput(1, normal_sop)
    xform_sop.setInput(0, normal_switch_sop)
    out_sop.setInput(0, xform_sop)
    # Temp node connections.
    fbx_restore_prim_groups_temp.setInput(0, file_temp_sop)
    fbx_attrib_delete_temp.setInput(0, fbx_restore_prim_groups_temp)
    is_fbx_switch_temp.setInput(0, file_temp_sop)
    is_fbx_switch_temp.setInput(1, fbx_attrib_delete_temp)
    out_temp.setInput(0, is_fbx_switch_temp)

    # Add script callback to source file import path hou.StringParmTemplate.
    parm_template_group = control_node.parmTemplateGroup()
    source_path = parm_template_group.find('%s_path' % node_name)
    script_callback = "%s;hou.node('%s').parm('input').set(1) if dynamite.is_path_fbx(hou.pwd().parm('%s').eval()) "\
                      "else hou.node('%s').parm('input').set(0)" % (
                        Dynamite.MODULE_IMPORT, is_fbx_switch.path(), '%s_path' % node_name, is_fbx_switch.path())
    source_path.setScriptCallback(script_callback)
    source_path.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    parm_template_group.replace('%s_path' % node_name, source_path)
    control_node.setParmTemplateGroup(parm_template_group)

    geo_node.layoutChildren()
    return geo_node


def create_output_group(node_name, group_type, control_node, suffix=''):
    """Creates output groups for retopo, reference and cage bake groups. Legacy and required mostly for .obj export.
    :type node_name: str
    :type group_type: str
    :type control_node: hou.ObjNode
    :type suffix: str
    :rtype: hou.ObjNode"""
    network_location = control_node.parm('network_location').eval()
    retopo_source_out_geo = hou.node(control_node.parm('retopo_source_out').eval()).geometry()
    prim_group_names = get_prim_group_names(retopo_source_out_geo)
    number_of_prim_groups = len(prim_group_names)

    obj_node = hou.node(network_location).createNode('geo')
    obj_node.setName(node_name)
    obj_node.setColor(DynamiteColor.GRAY_LIGHT)
    set_node_shape(obj_node, 6)
    obj_node.setDisplayFlag(False)
    obj_node.setSelectableInViewport(False)
    set_default_folders_hidden(obj_node.parmTemplateGroup())
    destroy_children(obj_node)

    object_merge = obj_node.createNode('object_merge')
    object_merge.setName('object_merge')
    object_merge.parm('numobj').set(number_of_prim_groups)
    object_path_suffix = 1
    for prim_group_name in prim_group_names:
        if group_type is not 'cage':
            group_obj_path = '%s/%s_%s' % (network_location, prim_group_name, group_type)
        else:
            group_obj_path = '%s/%s_cage' % (network_location, prim_group_name)
        object_merge.parm('objpath%d' % object_path_suffix).set(group_obj_path)
        object_path_suffix += 1

    add_suffix = obj_node.createNode('grouprename')
    add_suffix.setName('add_suffix')
    add_suffix.parm('group1').set('*')
    if group_type is 'retopo':
        add_suffix.parm('newname1').set('*%s' % control_node.parm('retopo_suffix').eval())
    if group_type is 'reference':
        add_suffix.parm('newname1').set('*%s' % control_node.parm('reference_suffix').eval())

    use_suffix = obj_node.createNode('switch')
    use_suffix.setName('use_suffix')
    if suffix is not '':
        use_suffix.parm('input').set(control_node.parm('name_correspondence'))

    out = obj_node.createNode('null')
    out.setName('OUT')
    out.setColor(DynamiteColor.BLACK)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)

    rop = obj_node.createNode('rop_geometry')
    rop.setName('export')
    if group_type is not 'cage':
        rop.parm('sopoutput').set(control_node.parm('%s_export_path' % group_type))
    else:
        rop.parm('sopoutput').set(control_node.parm('cage_export_path'))

    # Connections.
    add_suffix.setInput(0, object_merge)
    use_suffix.setInput(0, object_merge)
    use_suffix.setInput(1, add_suffix)
    out.setInput(0, use_suffix)
    rop.setInput(0, out)

    obj_node.layoutChildren()
    return obj_node


def create_retopo_group(prim_group, control_node):
    """Creates retopo bake hou.ObjNode. Adds prim group-related stuff to control node.
    :type prim_group: hou.PrimGroup
    :type control_node: hou.ObjNode
    :rtype: hou.ObjNode"""
    network_location = control_node.parm('network_location').eval()
    prim_group_name = prim_group.name()
    obj_node = hou.node(network_location).createNode('geo')
    obj_node.setName('%s_retopo' % prim_group_name)

    # Bundle-specific interface parameters.
    help = "How many iterations to subdivide, higher numbers give a smoother surface."
    disable_when = '{ subdivide == 0 }'
    subdiv_iterations_pt = hou.IntParmTemplate('%s_iterations' % prim_group_name, 'Iterations', 1, default_value=(0,),
                                               disable_when=disable_when, help=help)
    hide_when = '{ subdivide == 0 }'
    subdiv_iterations_pt.setConditional(hou.parmCondType.HideWhen, hide_when)

    help = "Translates the whole bake group."
    translate_pt = hou.FloatParmTemplate('%s_translate' % prim_group_name, 'Translate', 3, join_with_next=True,
                                         default_value=(0, 0, 0), help=help)

    help = "Takes you to predefined Edit SOP of the current cage object."
    script_callback = "%s;dynamite.edit_cage('%s', hou.node('%s'))" % (
        Dynamite.MODULE_IMPORT, prim_group_name, control_node.path())
    edit_cage_button = hou.ButtonParmTemplate('%s_edit_cage' % prim_group_name, 'Edit Cage',
                                              script_callback=script_callback,
                                              script_callback_language=hou.scriptLanguage.Python, help=help)

    help = "Offset distance of the cage from the retopo surface."
    peak_pt = hou.FloatParmTemplate('%s_peak_dist' % prim_group_name, 'Peak Distance', 1, help=help)
    peak_pt.setMaxValue(1.0)

    help = "Show %s retopo object." % (prim_group_name,)
    script_callback = "%s;dynamite.toggle_obj_display(hou.node('%s'), hou.node('%s'), '%s_retopo_display')" % (
        Dynamite.MODULE_IMPORT, obj_node.path(), control_node.path(), prim_group_name)
    retopo_display_toggle = hou.ToggleParmTemplate('%s_retopo_display' % prim_group_name, 'Show Retopo',
                                                   default_value=False, script_callback=script_callback,
                                                   script_callback_language=hou.scriptLanguage.Python, help=help)

    # Init only. Script callback added in create_reference_group().
    help = "Show %s reference object." % (prim_group_name,)
    reference_display_toggle = hou.ToggleParmTemplate('%s_reference_display' % prim_group_name, 'Show Reference',
                                                      default_value=False, help=help)

    # Init only. Script callback added in create_cage_group().
    help = "Show %s cage object." % (prim_group_name,)
    cage_display_toggle = hou.ToggleParmTemplate('%s_cage_display' % prim_group_name, 'Show Cage',
                                                 default_value=True, help=help)

    help = "Restores the cage object to default."
    script_callback = "%s;dynamite.reset_cage('%s', hou.node('%s'))" % (
        Dynamite.MODULE_IMPORT, prim_group_name, control_node.path())
    reset_changes_button = hou.ButtonParmTemplate('%s_reset_changes' % prim_group_name, 'Reset Changes',
                                                  join_with_next=True, script_callback=script_callback,
                                                  script_callback_language=hou.scriptLanguage.Python,
                                                  help=help)

    retopo_out_geo = hou.node(control_node.parm('retopo_source_out').eval()).geometry()
    all_prim_group_names = get_prim_group_names(retopo_out_geo)

    help = "Shows reference and cage objects of all bake groups."
    script_callback = "%s;dynamite.set_group_display(%s, False, True, True, hou.node('%s'))" % (
        Dynamite.MODULE_IMPORT, str(all_prim_group_names), control_node.path())
    show_reference_cages_button = hou.ButtonParmTemplate('%s_show_ref_cages' % prim_group_name,
                                                         'Show Reference and Cages', join_with_next=True,
                                                         script_callback=script_callback,
                                                         script_callback_language=hou.scriptLanguage.Python,
                                                         help=help)

    help = "Shows cage objects of all bake groups."
    script_callback = "%s;dynamite.set_group_display(%s, False, False, True, hou.node('%s'))" % (
        Dynamite.MODULE_IMPORT, str(all_prim_group_names), control_node.path())
    show_cages_only = hou.ButtonParmTemplate('%s_show_cages_only' % prim_group_name, 'Show Cages Only',
                                             join_with_next=True, script_callback=script_callback,
                                             script_callback_language=hou.scriptLanguage.Python, help=help)

    help = "Isolates the reference and cage objects of the current bake group."
    script_callback = "%s;dynamite.set_group_display(%s, False, False, False, hou.node('%s'));" \
                      "dynamite.set_group_display(('%s',), False, True, True, hou.node('%s'));" \
                      "dynamite.home()" %\
                      (Dynamite.MODULE_IMPORT, all_prim_group_names, control_node.path(),
                       prim_group_name, control_node.path())
    isolate_button = hou.ButtonParmTemplate('%s_isolate' % prim_group_name, 'Isolate',
                                            script_callback=script_callback,
                                            script_callback_language=hou.scriptLanguage.Python, help=help)

    folder = hou.FolderParmTemplate('%s_folder' % prim_group_name, prim_group_name, (
        subdiv_iterations_pt, translate_pt, edit_cage_button, peak_pt, retopo_display_toggle, reference_display_toggle,
        cage_display_toggle, reset_changes_button, show_reference_cages_button, show_cages_only, isolate_button),
                                    folder_type=hou.folderType.Simple, ends_tab_group=True)
    # folder.setEndsTabGroup(True)  # Uncomment if ends_tab_group in the constructor doesn't work.

    parm_template_group = control_node.parmTemplateGroup()
    parm_template_group.appendToFolder('Edit', folder)
    control_node.setParmTemplateGroup(parm_template_group)

    # Operators.
    destroy_children(obj_node)
    set_default_folders_hidden(obj_node.parmTemplateGroup())
    # obj_node.parmTemplateGroup(parm_template_group)
    obj_node.setColor(DynamiteColor.GRAY)
    obj_node.setDisplayFlag(bool(control_node.parm('%s_retopo_display' % prim_group_name).eval()))
    obj_node.setSelectableInViewport(bool(control_node.parm('%s_retopo_display' % prim_group_name).eval()))
    obj_node.moveToGoodPosition()
    obj_node.parm('shop_materialpath').set(control_node.parm('retopo_material').eval())

    object_merge = obj_node.createNode('object_merge')
    object_merge.setName('%s_object_merge' % prim_group_name)
    object_merge.parm('objpath1').set(prim_group.geometry().sopNode().path())
    object_merge.parm('group1').set(prim_group_name)

    xform = obj_node.createNode('xform')
    xform.setName('%s_xform' % prim_group_name)
    xform.parm('updatenmls').set(0)
    xform.parmTuple('t').set(control_node.parmTuple('%s_translate' % prim_group_name))

    triangulate = obj_node.createNode('divide')
    triangulate.setName('%s_triangulate' % prim_group_name)
    # triangulate.parm('convex').set(1)
    # triangulate.parm('usemaxsides').set(3)
    # triangulate.parm('numsides').set(3)
    # triangulate.parm('planar').set(1)
    # triangulate.parm('plantol').set(0.0001)
    # triangulate.parm('noslivers').set(0)
    # triangulate.parm('avoidsmallangles').set(0)
    # triangulate.parm('smooth').set(0)
    # triangulate.parm('brick').set(0)
    # triangulate.parm('removesh').set(0)
    # triangulate.parm('dual').set(0)

    triangulate_switch = obj_node.createNode('switch')
    triangulate_switch.setName('%s_triangulate_switch' % prim_group_name)
    triangulate_switch.parm('input').set(control_node.parm('triangulate'))

    export_scale = obj_node.createNode('xform')
    export_scale.setName('%s_export_scale' % prim_group_name)
    export_scale.parm('scale').set(control_node.parm('export_scale'))

    subdivide = obj_node.createNode('subdivide')
    subdivide.setName('%s_subdivide' % prim_group_name)
    subdivide.parm('algorithm').set(control_node.parm('algorithm'))
    subdivide.parm('iterations').set(control_node.parm('%s_iterations' % prim_group_name))

    subdivide_switch = obj_node.createNode('switch')
    subdivide_switch.setName('%s_subdivide_switch' % prim_group_name)
    subdivide_switch.parm('input').set(control_node.parm('subdivide'))

    out = obj_node.createNode('null')
    out.setName('%s_OUT' % prim_group_name)
    out.setColor(DynamiteColor.BLACK)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)

    # Connections
    xform.setInput(0, object_merge)
    export_scale.setInput(0, xform)
    subdivide.setInput(0, export_scale)
    subdivide_switch.setInput(0, export_scale)
    subdivide_switch.setInput(1, subdivide)
    triangulate.setInput(0, subdivide_switch)
    triangulate_switch.setInput(0, subdivide_switch)
    triangulate_switch.setInput(1, triangulate)
    out.setInput(0, triangulate_switch)

    obj_node.layoutChildren()
    return obj_node


def create_cage_group(prim_group, control_node, return_control=False):
    """Creates retopo cage hou.ObjNode. Updates prim group-related control node parameters.
    :type prim_group: hou.PrimGroup
    :type control_node: hou.ObjNode
    :type return_control: bool
    :rtype: hou.ObjNode"""
    network_location = control_node.parm('network_location').eval()
    prim_group_name = prim_group.name()

    # Group contents.
    obj_node = hou.node(network_location).createNode('geo')
    destroy_children(obj_node)
    set_default_folders_hidden(obj_node.parmTemplateGroup())
    obj_node.setName('%s_cage' % prim_group_name)
    obj_node.setColor(DynamiteColor.GRAY_LIGHT)
    obj_node.setDisplayFlag(bool(control_node.parm('%s_cage_display' % prim_group_name).eval()))
    obj_node.setSelectableInViewport(bool(control_node.parm('%s_cage_display' % prim_group_name).eval()))
    obj_node.parm('shop_materialpath').set(control_node.parm('cage_material').eval())

    object_merge = obj_node.createNode('object_merge')
    object_merge.setName('%s_object_merge' % prim_group_name)
    object_merge.parm('objpath1').set(control_node.parm('retopo_source_out'))
    object_merge.parm('group1').set(prim_group_name)

    material = obj_node.createNode('material')
    material.setName('%s_material' % prim_group_name)
    material.parm('shop_materialpath1').set(control_node.parm('cage_material').eval())

    xform = obj_node.createNode('xform')
    xform.setName('%s_xform' % prim_group_name)
    xform.parm('updatenmls').set(0)
    xform.parmTuple('t').set(control_node.parmTuple('%s_translate' % prim_group_name))

    normals = obj_node.createNode('normal')
    normals.setName('%s_normal' % prim_group_name)
    normals.parm('cuspangle').set(180)
    normals.parm('type').set(0)

    peak = obj_node.createNode('peak')
    peak.setName('%s_peak' % prim_group_name)
    peak.parm('updatenmls').set(0)
    peak.parm('dist').set(control_node.parm('%s_peak_dist' % prim_group_name))

    user_block_start = obj_node.createNode('null')
    user_block_start.setName('USER_BEGIN')
    user_block_start.setColor(DynamiteColor.GREEN)

    user_block_end = obj_node.createNode('null')
    user_block_end.setName('USER_END')
    user_block_end.setColor(DynamiteColor.GREEN)

    edit = obj_node.createNode('edit')
    edit.setName('%s_edit' % prim_group_name)
    edit.setColor(DynamiteColor.GOLD)

    retopo_merge = obj_node.createNode('object_merge')
    retopo_merge.setName('%s_retopo_merge' % prim_group_name)
    retopo_merge.parm('objpath1').set(
        '%s/%s_retopo/%s_triangulate' % (network_location, prim_group_name, prim_group_name))

    delete_material = obj_node.createNode('attribdelete')
    delete_material.setName('%s_shop_path_delete' % prim_group_name)
    delete_material.parm('primdel').set('shop_materialpath')

    # Remove commented lines if everything is ok with the Python implementation of the simplified 'topo_match'.
    # topology_match = obj_node.createNode('com.arturjzarek::exact_topology_match')
    topology_match = topo_match.create_node(obj_node)
    # topology_match.setName('%s_topology_match' % prim_group_name)
    # topology_match.parm('mode').set(1)

    topology_match_switch = obj_node.createNode('switch')
    topology_match_switch.setName('%s_match_topology' % prim_group_name)
    topology_match_switch.parm('input').set(control_node.parm('triangulate'))

    export_scale = obj_node.createNode('xform')
    export_scale.setName('%s_export_scale' % prim_group_name)
    export_scale.parm('scale').set(control_node.parm('export_scale'))

    subdivide = obj_node.createNode('subdivide')
    subdivide.setName('%s_subdivide' % prim_group_name)
    subdivide.parm('algorithm').set(control_node.parm('algorithm'))
    subdivide.parm('iterations').set(control_node.parm('%s_iterations' % prim_group_name))

    subdivide_switch = obj_node.createNode('switch')
    subdivide_switch.setName('%s_subdivide_switch' % prim_group_name)
    subdivide_switch.parm('input').set(control_node.parm('subdivide'))

    post_normals = obj_node.createNode('normal')
    post_normals.setName('%s_post_normals' % prim_group_name)
    post_normals.parm('cuspangle').set(180)
    post_normals.parm('type').set(0)

    out = obj_node.createNode('null')
    out.setName('%s_OUT' % prim_group_name)
    out.setColor(DynamiteColor.BLACK)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)

    # Connections.
    material.setInput(0, object_merge)
    normals.setInput(0, material)
    peak.setInput(0, normals)
    user_block_start.setInput(0, peak)
    user_block_end.setInput(0, user_block_start)
    edit.setInput(0, user_block_end)
    xform.setInput(0, edit)
    export_scale.setInput(0, xform)
    subdivide.setInput(0, export_scale)
    subdivide_switch.setInput(0, export_scale)
    subdivide_switch.setInput(1, subdivide)
    delete_material.setInput(0, retopo_merge)
    topology_match.setInput(0, subdivide_switch)
    topology_match.setInput(1, delete_material)
    topology_match_switch.setInput(0, subdivide_switch)
    topology_match_switch.setInput(0, subdivide_switch)
    topology_match_switch.setInput(1, topology_match)
    post_normals.setInput(0, topology_match_switch)
    out.setInput(0, post_normals)

    obj_node.layoutChildren()

    # Update control node parameters.
    # TODO: Externalize to function.
    script_callback = "%s;dynamite.toggle_obj_display(hou.node('%s'), hou.node('%s'), '%s_cage_display')" % (
        Dynamite.MODULE_IMPORT, obj_node.path(), control_node.path(), prim_group_name)
    parm_template_group = control_node.parmTemplateGroup()
    cage_display_toggle = parm_template_group.find('%s_cage_display' % prim_group_name)
    cage_display_toggle.setScriptCallback(script_callback)
    cage_display_toggle.setScriptCallbackLanguage(hou.scriptLanguage.Python)

    # Update current list of primitive groups.
    prim_groups_list = get_current_prim_groups(control_node)  # TODO: Remove the variable assignment.
    add_to_current_prim_groups(control_node, prim_group_name)

    parm_template_group.replace('%s_cage_display' % prim_group_name, cage_display_toggle)
    control_node.setParmTemplateGroup(parm_template_group)

    return obj_node if not return_control else (obj_node, control_node)


def create_reference_group(prim_group, control_node):
    """Creates reference bake hou.ObjNode.
    :type prim_group: hou.PrimGroup
    :type control_node: hou.ObjNode
    :rtype: hou.ObjNode"""
    network_location = control_node.parm('network_location').eval()
    prim_group_name = prim_group.name()
    obj_node = hou.node(network_location).createNode('geo')
    destroy_children(obj_node)
    set_default_folders_hidden(obj_node.parmTemplateGroup())
    obj_node.setName('%s_reference' % prim_group_name)
    obj_node.setColor(DynamiteColor.GRAY)
    obj_node.setDisplayFlag(bool(control_node.parm('%s_reference_display' % prim_group_name).eval()))
    obj_node.setSelectableInViewport(bool(control_node.parm('%s_reference_display' % prim_group_name).eval()))
    obj_node.moveToGoodPosition()

    object_merge = obj_node.createNode('object_merge')
    object_merge.setName('%s_object_merge' % prim_group_name)
    object_merge.parm('objpath1').set(prim_group.geometry().sopNode().path())
    object_merge.parm('group1').set(prim_group_name)

    xform = obj_node.createNode('xform')
    xform.setName('%s_xform' % prim_group_name)
    xform.parm('updatenmls').set(0)
    xform.parmTuple('t').set(control_node.parmTuple('%s_translate' % prim_group_name))

    export_scale = obj_node.createNode('xform')
    export_scale.setName('%s_export_scale' % prim_group_name)
    export_scale.parm('scale').set(control_node.parm('export_scale'))

    out = obj_node.createNode('null')
    out.setName('%s_OUT' % prim_group_name)
    out.setColor(DynamiteColor.BLACK)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)

    # Connections
    xform.setInput(0, object_merge)
    export_scale.setInput(0, xform)
    out.setInput(0, export_scale)

    # Update control node parameters.
    script_callback = "%s;dynamite.toggle_obj_display(hou.node('%s'), hou.node('%s'), '%s_reference_display')" % (
        Dynamite.MODULE_IMPORT, obj_node.path(), control_node.path(), prim_group_name)
    parm_template_group = control_node.parmTemplateGroup()
    reference_display_toggle = parm_template_group.find('%s_reference_display' % prim_group_name)
    reference_display_toggle.setScriptCallback(script_callback)
    reference_display_toggle.setScriptCallbackLanguage(hou.scriptLanguage.Python)

    parm_template_group.replace('%s_reference_display' % prim_group_name, reference_display_toggle)
    control_node.setParmTemplateGroup(parm_template_group)

    obj_node.layoutChildren()
    return obj_node


def append_to_folder(parm_template_group, folder, *parm_templates):
    """Appends a ParmTemplate object to a folder of a ParmTemplateGroup.
    :type parm_template_group: hou.ParmTemplateGroup
    :type folder: str
    :type parm_templates: hou.ParmTemplate
    :rtype: hou.ParmTemplateGroup"""
    for parm_template in parm_templates:
        parm_template_group.appendToFolder(folder, parm_template)
    return parm_template_group


def create_material(name, node_type, base_color, rough):
    """Creates and returns a material operator of a provided name, shader. Sets base color and roughness.
    If material already exists, it will be returned.
    :type name: str
    :type node_type: str
    :type base_color: tuple<float>
    :type rough: float
    :rtype: hou.ShopNode"""
    if hou.node('/mat/%s' % (name,)) is None:
        material = hou.node('/mat').createNode(node_type)
        material.parmTuple('basecolor').set(base_color)
        material.parm('rough').set(rough)
        material.setName(name)
        material.moveToGoodPosition()
        return material
    else:
        return hou.node('/mat/' + name)


def destroy_children(node):
    """Removes all children of a given operator."""
    for child in node.children():
        child.destroy()


def edit_cage(prim_group_name, control_node, dive_in=True):
    """Routines for cage editing.
    :type prim_group_name: str
    :type control_node: hou.ObjNode
    :type dive_in: bool"""
    network_location = control_node.parm('network_location').eval()
    obj_node = hou.node('%s/%s_cage' % (network_location, prim_group_name))
    cage_edit_node = hou.node('%s/%s_cage/%s_edit' % (network_location, prim_group_name, prim_group_name))
    # If user dives into the cage node and switches to Edit Handle but doesn't make any changes before leaving it...
    # Houdini removes the edit node, so it needs to be recreated.
    if cage_edit_node is None:
        # Re-create the node.
        cage_edit_node = hou.node('%s/%s_cage' % (network_location, prim_group_name)).createNode('edit')
        cage_edit_node.setName('%s_edit' % prim_group_name)
        cage_edit_node.setColor(DynamiteColor.GOLD)

        user_block_end = hou.node('%s/%s_cage/USER_END' % (network_location, prim_group_name))
        xform = hou.node('%s/%s_cage/%s_xform' % (network_location, prim_group_name, prim_group_name))

        cage_edit_node.setInput(0, user_block_end)
        xform.setInput(0, cage_edit_node)
        obj_node.layoutChildren()

    if dive_in:
        get_current_network_editor(hou.ui.curDesktop()).setCurrentNode(cage_edit_node)
        # Clear selection of all nodes.
        for child in hou.node('%s/%s_cage' % (network_location, prim_group_name)).children():
            child.setSelected(False)
            child.setCurrent(False)
        cage_edit_node.setSelected(True)
        cage_edit_node.setCurrent(True)


def copy_bake_groups(obj_nodes, find, replace, control_node, subnet_name='temp_fbx_export', display=True):
    """Creates a new subnet and copies all specified node into it.
    If subnet exists, all of its children will be destroyed first.
    :type obj_nodes: list[hou.ObjNode]
    :type find: str
    :type replace: str
    :type control_node: hou.ObjNode
    :type subnet_name: str
    :type display: bool
    :rtype: list[hou.ObjNode]"""
    network_location = control_node.parm('network_location').eval()
    subnet = hou.node('%s/%s' % (network_location, subnet_name))
    if subnet is None:
        subnet = hou.node('%s/' % network_location).createNode('subnet')
        subnet.setName(subnet_name)
        subnet.moveToGoodPosition()
    else:
        destroy_children(subnet)

    copy = subnet.copyItems(obj_nodes, channel_reference_originals=True, relative_references=False)
    for node in copy:
        node.setName(node.name().replace(find, replace))
        node.setDisplayFlag(display)
    return copy


def create_fbx_export_nodes(obj_nodes, find, replace_with, control_node):
    """Creates a subnetwork in the same path as the control_node.
    Then, creates one ObjNode per obj_node, containing object merge SOP that pulls geometry from the original node.
    Names of new ObjNodes are searched for 'find' and replaced by 'replace_with'.
    :type obj_nodes: list[hou.ObjNode]
    :type find: str
    :type replace_with: str
    :type control_node: hou.ObjNode
    :rtype: tuple[hou.ObjNode]"""
    network_location = control_node.parm('network_location').eval()

    subnet_name = 'fbx_temp_subnet'
    subnet = hou.node('%s/%s' % (network_location, subnet_name))
    if subnet is None:
        subnet = hou.node(network_location).createNode('subnet')
        subnet.setName(subnet_name)
    else:
        destroy_children(subnet)

    copies = []
    for obj_node in obj_nodes:
        node = subnet.createNode('geo')
        node.setName(obj_node.name().replace(find, replace_with))
        destroy_children(node)
        object_merge = node.createNode('object_merge')
        object_merge.parm('objpath1').set(obj_node.path())
        copies.append(node)
    return tuple(copies)


def is_path_fbx(path):
    """Returns True if the file extension in a given path is FBX or false if it's different.
    :type path: str"""
    path_ext = os.path.splitext(path)[-1].lower()
    if path_ext == '.fbx':
        return True
    else:
        return False


def create_fbx_rop(prefix):
    """Creates a new filmboxfbx ROP. If it finds ROP of the same name, it will remove it first.
    :type prefix: str
    :rtype: hou.RopNode"""
    fbx_rop = hou.node('/out/%s_fbx_export' % prefix)
    if fbx_rop is None:
        fbx_rop = hou.node('/out').createNode('filmboxfbx')
        fbx_rop.setName('%s_fbx_export' % prefix)
    return fbx_rop


def export_fbx(group_type, suffix, control_node):
    """Deals with FBX export. Creates necessary nodes and removes them after the operation is complete.
    :type group_type: str
    :type suffix: str
    :type control_node: hou.ObjNode"""
    network_location = control_node.parm('network_location').eval()
    prim_group_names = control_node.parm('prim_groups').eval().split(' ')
    obj_nodes = []
    for name in prim_group_names:
        obj_nodes.append(hou.node('%s/%s_%s' % (network_location, name, group_type)))
    subnet = create_fbx_export_nodes(obj_nodes, '_%s' % group_type, '%s' % suffix, control_node)[0].parent()
    subnet.setColor(DynamiteColor.RED)
    fbx_rop = create_fbx_rop('retopo')
    export_path = control_node.parm('%s_export_path' % group_type).eval()
    fbx_rop.parm('sopoutput').set(export_path)
    fbx_rop.parm('startnode').set(subnet.path())
    fbx_rop.parm('sdkversion').set(control_node.parm('sdk_version').evalAsString())
    fbx_rop.parm('exportkind').set(control_node.parm('fbx_ascii').eval())
    fbx_rop.parm('execute').pressButton()
    fbx_rop.destroy()
    subnet.destroy()


def export(retopo, reference, cage, control_node):
    """Export routines.
    Arguments:
        retopo - should retopo groups be exported?
        reference - should reference groups be exported?
        cage - should cage groups be exported?
        control_node - reference to Dynamite control node.
    :type retopo: bool
    :type reference: bool
    :type cage: bool
    :type control_node: hou.ObjNode"""
    operation = hou.InterruptableOperation('Exporting', long_operation_name='Initializing...',
                                           open_interrupt_dialog=True)
    if control_node.parm('name_correspondence').eval() is 1:
        retopo_suffix = control_node.parm('retopo_suffix').eval()
        reference_suffix = control_node.parm('reference_suffix').eval()
    else:
        retopo_suffix = ''
        reference_suffix = ''

    with operation:
        if retopo:
            operation.updateLongProgress(long_op_status='Exporting Retopo')
            export_path = control_node.parm('retopo_export_path').eval()

            if is_path_fbx(export_path):
                export_fbx(Dynamite.RETOPO_GROUP, retopo_suffix, control_node)

            else:
                export_sop = hou.node('%s/export' % control_node.parm('retopo_output_obj').eval())
                export_sop.parm('execute').pressButton()

        if reference:
            operation.updateLongProgress(0.33, long_op_status='Exporting Reference')
            export_path = control_node.parm('reference_export_path').eval()

            if is_path_fbx(export_path):
                export_fbx(Dynamite.REFERENCE_GROUP, reference_suffix, control_node)

            else:
                export_sop = hou.node('%s/export' % control_node.parm('reference_output_obj').eval())
                export_sop.parm('execute').pressButton()

        if cage:
            operation.updateLongProgress(0.66, long_op_status='Exporting Cage')
            export_path = control_node.parm('cage_export_path').eval()

            if is_path_fbx(export_path):
                export_fbx(Dynamite.CAGE_GROUP, '', control_node)

            else:
                export_sop = hou.node('%s/export' % control_node.parm('cage_output_obj').eval())
                export_sop.parm('execute').pressButton()


def path_exists(path):
    """Returns true if a given path exists. It can be a path to file or op:/ to an existing operator.
    :type path: str
    :rtype: bool"""
    if path.startswith('op:/'):
        if hou.node(path[3:]) is None:
            return False
        else:
            return True
    if os.path.isfile(path):
        return True
    else:
        return False


def find_prim_group(prim_group_name, prim_groups):
    """Given a primitive group name and a tuple of primitive group objects,
    find and return the specific primitive group from the tuple.
    :type prim_group_name: str
    :type prim_groups: tuple[hou.PrimGroup]
    :rtype: hou.PrimGroup"""
    for prim_group in prim_groups:
        if prim_group.name() == prim_group_name:
            return prim_group
    return None


def get_current_network_editor(desktop):
    """Returns the currently active Network Editor window.
    :type desktop: hou.Desktop
    :rtype: hou.NetworkEditor"""
    for pane in desktop.paneTabs():
        if isinstance(pane, hou.NetworkEditor) and pane.isCurrentTab():
            return pane


def get_multiparm_index(multi_parm, path):
    """Returns an index of a multiparm item."""
    parms = multi_parm.multiParmInstances()
    obj_paths = [parm for parm in parms if 'objpath' in parm.name()]
    for parm in obj_paths:
        if path in parm.evalAsString():
            index = parm.multiParmInstanceIndices()[0] / 4  # TODO: Remove the assignment.


def get_prim_group_names(geo, sort=True):
    """Returns a list of primitive groups in a given hou.Geometry. Sorts the list if sorted=True.
    :type geo: hou.Geometry
    :type sort: bool
    :rtype: list[str]"""
    prim_group_names = []
    for prim_group in geo.primGroups():
        prim_group_names.append(prim_group.name())
    return sorted(prim_group_names) if sort else prim_group_names


def home():
    """Frames and homes the viewport on visible geometry."""
    viewer = toolutils.sceneViewer()
    viewport = viewer.curViewport()
    viewport.draw()
    viewport.homeAll()


def home_network(path, frame_percentage=0.2):
    """Homes the Network Editor on nodes inside a given path.
    Arguments:
        path - nodes inside this path will be framed in the network editor.
        frame_percentage - percentage of the bounding box which will be used as a framing border (distance to borders).
    :type path: str
    :type frame_percentage: float"""
    network_editor = get_current_network_editor(hou.ui.curDesktop())
    nodes = hou.node(path).children()
    pos_x = []
    pos_y = []
    for node in nodes:
        position = node.position()
        pos_x.append(position[0])
        pos_y.append(position[1])
    #frame_size = ((max(pos_x) - min(pos_x)), (max(pos_y) - min(pos_y)))
    frame_size = (frame_percentage * (max(pos_x) - min(pos_x)), frame_percentage * (max(pos_y) - min(pos_y)))
    bounds = hou.BoundingRect(min(pos_x) - frame_size[0] / 2,
                              min(pos_y) - frame_size[1] / 2,
                              max(pos_x) + frame_size[0] / 2,
                              max(pos_y) + frame_size[1] / 2)
    network_editor.setVisibleBounds(bounds, transition_time=0.5, max_scale=100)


def primitive_groups_match(geo1, geo2):
    """Checks if primitive groups of two geometries match.
    :type geo1: hou.Geometry()
    :type geo2: hou.Geometry()"""
    error_no_match = "ERROR: Primitive groups of retopo and reference files don't match."
    error_no_groups = "ERROR: No primitive groups in both: retopo and reference files."

    if len(geo1.primGroups()) != len(geo2.primGroups()):
        hou.ui.displayMessage(error_no_match)
        return False
    if ((len(geo1.primGroups()) == 0) and (len(geo2.primGroups()) != 0)
            or ((len(geo1.primGroups()) != 0) and (len(geo2.primGroups()) == 0))):
        hou.ui.displayMessage(error_no_match)
        return False
    if (len(geo1.primGroups()) == 0) and (len(geo2.primGroups()) == 0):
        hou.ui.displayMessage(error_no_groups)
        return False

    prim_groups1 = []
    prim_groups2 = []

    for prim_group in geo1.primGroups():
        prim_groups1.append(prim_group.name())
    for prim_group in geo2.primGroups():
        prim_groups2.append(prim_group.name())

    if sorted(prim_groups1) == sorted(prim_groups2):
        return True
    else:
        hou.ui.displayMessage(error_no_match)
        return False


def reset_cage(prim_group_name, control_node):
    """Removes the cage group of a specific primitive group and recreates it from scratch.
    :type prim_group_name: str
    :type control_node: hou.ObjNode"""
    network_location = control_node.parm('network_location').eval()
    reference_obj = hou.node('%s/%s_reference' % (network_location, prim_group_name))
    cage_node = hou.node('%s/%s_cage' % (network_location, prim_group_name))
    position = cage_node.position()
    cage_node.destroy()
    retopo_source_out_sop = hou.node(control_node.parm('retopo_source_out').eval())
    prim_group = find_prim_group(prim_group_name, retopo_source_out_sop.geometry().primGroups())
    cage_obj = create_cage_group(prim_group, control_node)
    cage_obj.setPosition(position)
    cage_obj.setInput(0, reference_obj)

    # Reset cage-specific control node parameters.
    control_node.parmTuple('%s_translate' % prim_group_name).set((0, 0, 0))
    control_node.parm('%s_peak_dist' % prim_group_name).set(0)


def set_default_folders_hidden(parm_template_group, hide=True):
    """Sets visibility of default folders of the provided ParmTemplateGroup ('Transform', 'Render' and 'Misc').
    :type parm_template_group: hou.ParmTemplateGroup
    :type hide: bool"""
    parm_template_group.hideFolder('Transform', hide)
    parm_template_group.hideFolder('Render', hide)
    parm_template_group.hideFolder('Misc', hide)
    parm_template_group.sourceNode().setParmTemplateGroup(parm_template_group)


def set_group_display(prim_group_names, show_retopo, show_reference, show_cage, control_node):
    """Sets visibility of bundle members for a given primitive group.
    :type prim_group_names: tuple[str]
    :type show_retopo: bool
    :type show_reference: bool
    :type show_cage: bool
    :type control_node: hou.ObjNode"""
    network_location = control_node.parm('network_location').eval()

    for prim_group_name in prim_group_names:
        retopo_obj = hou.node('%s/%s_retopo' % (network_location, prim_group_name))
        reference_obj = hou.node('%s/%s_reference' % (network_location, prim_group_name))
        cage_obj = hou.node('%s/%s_cage' % (network_location, prim_group_name))

        retopo_obj.setDisplayFlag(show_retopo)
        reference_obj.setDisplayFlag(show_reference)
        cage_obj.setDisplayFlag(show_cage)

        retopo_display_toggle = control_node.parm('%s_retopo_display' % prim_group_name)
        reference_display_toggle = control_node.parm('%s_reference_display' % prim_group_name)
        cage_display_toggle = control_node.parm('%s_cage_display' % prim_group_name)
        retopo_display_toggle.set(show_retopo)
        reference_display_toggle.set(show_reference)
        cage_display_toggle.set(show_cage)


def toggle_obj_display(node, control_node, parm_name):
    """Toggles display flag of a given hou.ObjNode and updates its corresponding display checkbox in the control node.
    :type node: hou.ObjNode
    :type control_node: hou.ObjNode
    :type parm_name: str"""
    if node.isDisplayFlagSet():
        node.setDisplayFlag(False)
        control_node.parm(parm_name).set(0)
    else:
        node.setDisplayFlag(True)
        control_node.parm(parm_name).set(1)


def update_network(control_node):
    """Updates all bake groups. Deletes groups that are missing in the new asset version, adds those that are new.
    :type control_node: hou.ObjNode"""
    network_location = control_node.parm('network_location').eval()
    retopo_file = hou.node(control_node.parm('retopo_source_file_sop').eval())
    reference_file = hou.node(control_node.parm('reference_source_file_sop').eval())
    retopo_temp = hou.node(control_node.parm('retopo_source_temp_file_sop').eval())
    reference_temp = hou.node(control_node.parm('reference_source_temp_file_sop').eval())
    retopo_source_out = hou.node(control_node.parm('retopo_source_out').eval())
    retopo_source_temp_out = hou.node('%s/OUT_TEMP' % (control_node.parm('retopo_source').eval()))
    reference_source_out = hou.node(control_node.parm('reference_source_out').eval())
    reference_source_temp_out = hou.node('%s/OUT_TEMP' % (control_node.parm('reference_source').eval()))
    retopo_is_fbx_temp_switch = hou.node('%s/is_fbx_temp' % (control_node.parm('retopo_source').eval()))
    reference_is_fbx_temp_switch = hou.node('%s/is_fbx_temp' % (control_node.parm('reference_source').eval()))

    retopo_temp.parm('file').set(control_node.parm('retopo_source_path').eval())
    reference_temp.parm('file').set(control_node.parm('reference_source_path').eval())

    retopo_temp.parm('reload').pressButton()
    reference_temp.parm('reload').pressButton()

    retopo_temp.cook()
    reference_temp.cook()

    if is_path_fbx(control_node.parm('retopo_source_path').eval()):
        retopo_is_fbx_temp_switch.parm('input').set(1)
    else:
        retopo_is_fbx_temp_switch.parm('input').set(0)
    if is_path_fbx(control_node.parm('reference_source_path').eval()):
        reference_is_fbx_temp_switch.parm('input').set(1)
    else:
        reference_is_fbx_temp_switch.parm('input').set(0)

    if not primitive_groups_match(retopo_source_temp_out.geometry(), reference_source_temp_out.geometry()):
        return
    retopo_file.parm('file').set(control_node.parm('retopo_source_path').eval())
    reference_file.parm('file').set(control_node.parm('reference_source_path').eval())

    parm_template_group = control_node.parmTemplateGroup()

    old_prim_group_names = control_node.parm('prim_groups').eval().split(' ')
    new_prim_group_names = get_prim_group_names(retopo_is_fbx_temp_switch.geometry())

    # Remove non-existing bake bundles.
    retopo_output_object_merge = hou.node('%s/object_merge' % control_node.parm('retopo_output_obj').eval())
    reference_output_object_merge = hou.node('%s/object_merge' % control_node.parm('reference_output_obj').eval())
    cage_output_object_merge = hou.node('%s/object_merge' % control_node.parm('cage_output_obj').eval())

    candidates_removal = sorted(list(set(old_prim_group_names) - set(new_prim_group_names)))
    for candidate in candidates_removal:
        # Remove corresponding multiParms from output nodes.
        # Retopo output multiParm.
        candidate_path = '%s/%s_retopo' % (network_location, candidate)
        retopo_object_merge_multiparm = retopo_output_object_merge.parm('numobj')
        remove_from_multiparm(retopo_object_merge_multiparm, 'objpath', candidate_path)
        # Reference output multiParm.
        candidate_path = '%s/%s_reference' % (network_location, candidate)
        reference_object_merge_multiparm = reference_output_object_merge.parm('numobj')
        remove_from_multiparm(reference_object_merge_multiparm, 'objpath', candidate_path)
        # Cage output multiParm.
        candidate_path = '%s/%s_cage' % (network_location, candidate)
        cage_object_merge_multiparm = cage_output_object_merge.parm('numobj')
        remove_from_multiparm(cage_object_merge_multiparm, 'objpath', candidate_path)
        # Remove the bake bundle.
        hou.node('%s/%s_retopo' % (network_location, candidate)).destroy()
        hou.node('%s/%s_reference' % (network_location, candidate)).destroy()
        hou.node('%s/%s_cage' % (network_location, candidate)).destroy()
        remove_from_current_prim_groups(control_node, candidate)
        parm_template_group.remove('%s_folder' % candidate)

    control_node.setParmTemplateGroup(parm_template_group)

    # Add new bake bundles.
    retopo_file.parm('reload').pressButton()
    reference_file.parm('reload').pressButton()
    candidates_add = sorted(list(set(new_prim_group_names) - set(old_prim_group_names)))
    for candidate in candidates_add:
        prim_group = retopo_source_out.geometry().findPrimGroup(candidate)
        retopo_group = create_retopo_group(prim_group, control_node)
        prim_group = reference_source_out.geometry().findPrimGroup(candidate)
        reference_group = create_reference_group(prim_group, control_node)
        prim_group = retopo_source_out.geometry().findPrimGroup(candidate)
        cage_group = create_cage_group(prim_group, control_node)
        reference_group.setInput(0, retopo_group)
        cage_group.setInput(0, reference_group)

        # Add corresponding multiParms to output nodes.
        # TODO: Externalize to function.
        # Retopo output multiparm.
        candidate_path = '%s/%s_retopo' % (network_location, candidate)
        retopo_object_merge_multiparm = retopo_output_object_merge.parm('numobj')
        numobj = retopo_object_merge_multiparm.eval() + 1
        retopo_object_merge_multiparm.set(numobj)
        retopo_output_object_merge.parm('objpath%d' % numobj).set(candidate_path)

        # Reference output multiparm.
        candidate_path = '%s/%s_reference' % (network_location, candidate)
        reference_object_merge_multiparm = reference_output_object_merge.parm('numobj')
        numobj = reference_object_merge_multiparm.eval() + 1
        reference_object_merge_multiparm.set(numobj)
        reference_output_object_merge.parm('objpath%d' % numobj).set(candidate_path)

        # Cage output multiparm.
        candidate_path = '%s/%s_cage' % (network_location, candidate)
        cage_object_merge_multiparm = cage_output_object_merge.parm('numobj')
        numobj = cage_object_merge_multiparm.eval() + 1
        cage_object_merge_multiparm.set(numobj)
        cage_output_object_merge.parm('objpath%d' % numobj).set(candidate_path)

        add_to_current_prim_groups(control_node, candidate)

    update_display_buttons(control_node)
    hou.node(network_location).layoutChildren()
    home_network(network_location)


def remove_from_multiparm(multi_parm, parm_name, value):
    """Removes instance from multiparm. Hardcoded for object_merge SOP multiparms.
    :type multi_parm: hou.Parm
    :type parm_name: str
    :type value: str"""
    instances = multi_parm.multiParmInstances()
    parms = [parm for parm in instances if parm_name in parm.name()]
    for parm in parms:
        if value in parm.evalAsString():
            index = parm.multiParmInstanceIndices()[0] / 4
            multi_parm.removeMultiParmInstance(index)
            break


def update_display_buttons(control_node):
    """Updates bundle display buttons on the control node. Required after performing network update.
    :type control_node: hou.ObjNode"""
    retopo_source_out = hou.node(control_node.parm('retopo_source_out').eval())
    prim_groups = retopo_source_out.geometry().primGroups()
    prim_group_names = sorted([prim_group.name() for prim_group in prim_groups])

    parm_template_group = control_node.parmTemplateGroup()

    for prim_group in prim_groups:
        prim_group_name = prim_group.name()

        # Show reference and cages button.
        script_callback = "%s;dynamite.set_group_display(%s, False, True, True, hou.node('%s'))" % (
            Dynamite.MODULE_IMPORT, str(prim_group_names), control_node.path())
        button = parm_template_group.find('%s_show_ref_cages' % prim_group_name)
        button.setScriptCallback(script_callback)
        parm_template_group.replace(button.name(), button)

        # Show cages only button.
        script_callback = "%s;dynamite.set_group_display(%s, False, False, True, hou.node('%s'))" % (
            Dynamite.MODULE_IMPORT, str(prim_group_names), control_node.path())
        button = parm_template_group.find('%s_show_cages_only' % prim_group_name)
        button.setScriptCallback(script_callback)
        parm_template_group.replace(button.name(), button)

        # Isolate button.
        script_callback = "%s;dynamite.set_group_display(%s, False, False, False, hou.node('%s'));" \
                          "dynamite.set_group_display(('%s',), False, True, True, hou.node('%s'));" \
                          "dynamite.home()" % \
                          (Dynamite.MODULE_IMPORT, prim_group_names, control_node.path(),
                           prim_group_name, control_node.path())

        button = parm_template_group.find('%s_isolate' % prim_group_name)
        button.setScriptCallback(script_callback)
        parm_template_group.replace(button.name(), button)

    control_node.setParmTemplateGroup(parm_template_group)


def get_current_prim_groups(control_node):
    """Returns the list of current primitive groups. Returns None if there are no primitive groups.
    :type control_node: hou.ObjNode
    :rtype: list[str]"""
    if control_node.parm('prim_groups').eval() is '':
        return None
    else:
        return control_node.parm('prim_groups').eval().split(' ')


def add_to_current_prim_groups(control_node, prim_group_name):
    """Adds a primitive group name to the list of current primitive group names.
    :type control_node: hou.ObjNode
    :type prim_group_name: str"""
    prim_groups_list = get_current_prim_groups(control_node)
    if prim_groups_list is None:
        prim_groups_list = []
    if prim_group_name not in prim_groups_list:
        prim_groups_list.append(prim_group_name)
    control_node.parm('prim_groups').set(' '.join(sorted(prim_groups_list)))


def remove_from_current_prim_groups(control_node, prim_group_name):
    """Removes a primitive group name from the list of current primitive group names.
    :type control_node: hou.ObjNode
    :type prim_group_name: str"""
    prim_groups_list = get_current_prim_groups(control_node)
    if prim_groups_list is None or prim_group_name not in prim_groups_list:
        return
    if prim_group_name in prim_groups_list:
        prim_groups_list.remove(prim_group_name)
        set_current_prim_groups(control_node, prim_groups_list)


def set_current_prim_groups(control_node, prim_group_names):
    """Sets current primitive names list to a certain value.
    :type control_node: hou.ObjNode
    :type prim_group_names: list[str]"""
    control_node.parm('prim_groups').set(' '.join(sorted(prim_group_names)))


def set_node_shape(node, shape):
    """Sets shape of a node.
    Arguments:
        node - node that will be reshaped.
        shape - shape indes from NetworkEditor.nodeShapes()
    :type node: hou.Node
    :type shape: int"""
    editor = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
    shapes = editor.nodeShapes()
    node.setUserData('nodeshape', shapes[shape])


if __name__ == '__main__':
    print('You must run this tool from the shelf.')
    sys.exit(1)
