# -*- coding: utf-8 -*-

# ===== topo_match.py
#
# Copyright (c) 2018 Artur J. Żarek
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

"""This module creates a subnetwork that is used by dynamite.py module
to match triangulation of retopo mesh to cage mesh.
"""
import sys
import dynamite


def create_node(parent):
    """Creates the subnetwork and all of the nodes to do the job.
    Arguments:
        parent - path to parent hou.ObjNode.
    Returns the subnetwork hou.SopNode.
    :type parent: hou.ObjNode
    :rtype: hou.SopNode"""
    subnet = parent.createNode('subnet')
    subnet.setName('topo_match')

    point_wrangle = subnet.createNode('attribwrangle')
    point_wrangle.setName('match_point_positions')
    point_wrangle.parm('class').set(2)
    snippet = """int success;
@P = pointattrib(1, "P", @ptnum, success);"""
    point_wrangle.parm('snippet').set(snippet)

    attribdelete = subnet.createNode('attribdelete')
    attribdelete.setName('delete_non_crucial_attribs')
    attribdelete.parm('ptdel').set('* ^P ^N')
    attribdelete.parm('vtxdel').set('* ^N ^uv')
    attribdelete.parm('primdel').set('*')
    attribdelete.parm('dtldel').set('*')

    delete_groups = subnet.createNode('groupdelete')
    delete_groups.setName('remove_source_groups')
    delete_groups.parm('group1').set('*')

    group_transfer = subnet.createNode('grouptransfer')
    group_transfer.setName('transfer_groups')
    group_transfer.parm('primgroups').set('*')
    group_transfer.parm('pointgroups').set('*')
    group_transfer.parm('edgegroups').set('*')

    normals = subnet.createNode('normal')
    normals.parm('cuspangle').set(180)

    out = subnet.createNode('null')
    out.setColor(dynamite.DynamiteColor.BLACK)
    out.setName('OUT')
    out.setDisplayFlag(True)
    out.setRenderFlag(True)

    # Connections.
    point_wrangle.setInput(0, subnet.indirectInputs()[1])
    point_wrangle.setInput(1, subnet.indirectInputs()[0])
    attribdelete.setInput(0, point_wrangle)
    delete_groups.setInput(0, attribdelete)
    group_transfer.setInput(0, delete_groups)
    group_transfer.setInput(1, subnet.indirectInputs()[0])
    normals.setInput(0, group_transfer)
    out.setInput(0, normals)

    subnet.layoutChildren()
    return subnet


if __name__ == '__main__':
    print('You must run this tool from the shelf.')
    sys.exit(1)
