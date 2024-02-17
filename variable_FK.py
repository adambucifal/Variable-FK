# Adam's Variable FK Script

import maya.cmds as cmds
import maya.mel as mel
from maya.api.OpenMaya import MGlobal


# Variables for node naming
system_name = "trunk_var_fk"
side = "__"
suffix = True
    
def name_object(name="__", node_name="__", include_system_name=True):
    """
    Produces a name and adds the suffix/prefix accordingly
    For naming, enter "__" in any param that will not be included.
    :param name: string, base name for the object (ex. shoulder_ctrl)
    :param node_name: string, type of node 
        (ex. plusMinusAverage -> pma - shoulder_ctrl_pma)
    
    Class variables:
    :side: string, which side the object is on 
        (ex. l, lf, left, r, rt, right). "__" If it is center 
    :suffix: Bool, if True places the side at the end of the string, 
        if False places the side at the beginning
    :system_name: string, name of the system (ex. var_fk)
    :return name: string, name created by the function
    """
    if suffix is True:
        if include_system_name is True:
            name = f"{name}_{system_name}_{node_name}_{side}"
        else:
            name = f"{name}_{node_name}_{side}"
    else:
        if include_system_name is True:
            name = f"{side}_{name}_{system_name}_{node_name}"
        else:
            name = f"{side}_{name}_{node_name}"

    return name.replace("___", "")
    
    
def create_nurbs_surface(joints):
    """
    Creates a nurbs surface based on an input curve
    :param joints: list of strings, names of the input joints
    :return nurbs_surface: string, name of the
        created nurbs surface
    """
    # Check joints
    if len(joints) < 3:
        cmds.error("Please select at least 3 input joints")

    if any(cmds.nodeType(jnt) != "joint" for jnt in joints):
        cmds.error("Select only joints")

    joint_positions = [
        cmds.xform(jnt, query=True, translation=True, worldSpace=True)
        for jnt in joints
    ]
    crv = cmds.curve(point=joint_positions, degree=3, name="temp_variable_fk_curve")

    # Setup for loft
    cmds.move(5,0,0, crv)
    duplicated_curve = cmds.duplicate(crv)[0]
    cmds.move(-5,0,0, duplicated_curve)

    # Create nurbs surface
    nurbs_surface = cmds.loft(
        crv,
        duplicated_curve,
        constructionHistory=False,
        name=name_object("surface"),
    )[0]

    cmds.delete(duplicated_curve, crv)
    return nurbs_surface

def create_node(type, name, connect_attrs=None, set_attrs=None):
    """
    Creates a node and connects/sets its inital attributes
    NOTE: when entering the name of the attributes,
        enter '*' (asterisks) to access the created node
    :param type: string, type of node to create
        (plusMinusAverage, transform, etc.)
    :param name: string, name of the node
    :param connect_attrs: list of tuples containing strings,
        the source attribute name and the target
        attribute name to connect it to
    :param set_attrs: list of tuples [(str, float/int)],
        the attribute name and the value to set it to
    :return node: string, name of the created node

    Examples:
        create_node(
            type="multiplyDivide",
            set_attrs=[("*.input1X", 72),("*.input1Y", 427)]
        )
        create_node(
            type="multiplyDivide",
            set_attrs=[("*.input1X", "*.input2X"),
                ("*.input1Y", "*.input2Y")]
        )
    """
    # Creates the specified node
    node = cmds.createNode(type, name=name)
    # Lambda function to add the new node to the attribute name
    filter_name = lambda string: string.replace("*", node)

    if connect_attrs is not None:
        # Filters the connect attribute list
        filter_connect_attrs = [
            (filter_name(attribute[0]), filter_name(attribute[1]))
            for attribute in connect_attrs
        ]
        # Connects attributes

        for connect_attr_set in filter_connect_attrs:
            cmds.connectAttr(*connect_attr_set)

    if set_attrs is not None:
        # Filters the set attribute list
        filter_set_attrs = [
            (filter_name(attribute[0]), attribute[1])
            for attribute in set_attrs
        ]
        # Sets attributes
        for set_attrs in filter_set_attrs:
            cmds.setAttr(*set_attrs)

    return node

def create_offset_group(name, target):
    target_original_parent = cmds.listRelatives(target, parent=True)

    offset_group = cmds.group(
        empty=True,
        name=name_object(node_name=name)
    )
    target_location = cmds.xform(target, query=True, matrix=True, worldSpace=True)
    cmds.xform(offset_group, matrix=target_location, worldSpace=True)
    cmds.parent(target, offset_group)
    if target_original_parent:
        cmds.parent(offset_group, target_original_parent[0])
    return offset_group

def build_variable_fk(
		number_of_controls=3, 
		control_normal=[1,0,0], 
		control_size=22
	):
    """
    Builds variable FK system
    :param number_of_controls: int, number of controls for the system
    :param control_normal: list of 3 floats, vector that controls
         where the control shape is pointing when it is created
    """
    # Gets and checks the selection
    selection = cmds.ls(selection=True, type="joint")
    if not selection:
        cmds.error("Nothing selected")

    # Create nurbs surface
    nurbs_surface = create_nurbs_surface(selection)
    cmds.hide(nurbs_surface)
    nurbs_shape = cmds.listRelatives(nurbs_surface, shapes=True)[0]

    # Empty list to store the control groups
    control_groups = []

    for value in range(1, number_of_controls+1):
        # Defines current values for node naming and follicle position
        current_value = value / (number_of_controls+1)
        current_node_name = lambda label: name_object(
            node_name=f"0{value}_{label}"
        )
        # Creates a control
        control_curve = cmds.circle(
            name=current_node_name("ctrl"),
            radius=control_size,
            constructionHistory=False,
            normal=control_normal,
        )[0]
        # Lock unused attributes
        [
			cmds.setAttr(
				f"{control_curve}.{channel}{axis}", 
				keyable=False, 
				channelBox=False, 
				lock=True,
			) 
			for axis in ["X", "Y", "Z"] 
			for channel in ["translate", "scale"]
        ] 
        
        # Creates the offset and control control
        control_group = cmds.group(name=current_node_name("ctrl_grp"))
        control_groups.append((control_curve, control_group))

        # Adds attributes to the control
        for attr in [("position", current_value, 0, 1), ("falloff", 0.2, 0.1, 0.5)]:
            cmds.addAttr(
                control_curve,
                defaultValue=attr[1],
                longName=attr[0],
                minValue=attr[2],
                maxValue=attr[3],
            )
            # Makes the attribute visible in the channel box
            cmds.setAttr(f"{control_curve}.{attr[0]}", keyable=True)

        # Setup the joints effected attribute on the control
        cmds.addAttr(
            control_curve, longName="numOfJointsEffected", attributeType="float"
        )
        cmds.setAttr(f"{control_curve}.numOfJointsEffected", keyable=True)


        joints_effected_multi = create_node(
            type="multiplyDivide",
            name=current_node_name("ctrl_jnts_effected_multi"),
            connect_attrs=[(f"{control_curve}.falloff", "*.input1X")],
            set_attrs=[("*.input2X", 2.0)],
        )
        joint_effected_remap = create_node(
            type="remapValue",
            name=current_node_name("ctrl_jnts_effected_remap"),
            connect_attrs=[
                (f"{joints_effected_multi}.outputX", "*.inputValue"),
                (f"*.outValue", f"{control_curve}.numOfJointsEffected")
            ],
            set_attrs=[("*.outputMin", 1), ("*.outputMax", len(selection))]
        )

        # Connect Follicle to surface
        #'*' represents the created node in the function
        follicle = create_node(
            type="follicle",
            name=current_node_name("follicleShape"),
            connect_attrs=[
                (f"{control_curve}.position", "*.parameterV"),
                (f"{nurbs_shape}.local", "*.inputSurface"),
                (f"{nurbs_shape}.worldMatrix", "*.inputWorldMatrix"),
            ],
            set_attrs=[(f"*.parameterU", 0.5)],
        )
        # Gets follicle transform
        follicle_transform = cmds.listRelatives(follicle, parent=True)[0]
        follicle_transform = cmds.rename(
            follicle_transform, current_node_name("follicle")
        )
        # Connects follicle shape to the follicle transform
        cmds.connectAttr(
            f"{follicle}.outRotate", f"{follicle_transform}.rotate"
        )
        cmds.connectAttr(
            f"{follicle}.outTranslate", f"{follicle_transform}.translate"
        )
        # Places the control at the follicle's location
        follicle_position = cmds.xform(
            follicle_transform, query=True, matrix=True, worldSpace=True
        )
        cmds.xform(control_group, matrix=follicle_position, worldSpace=True)

        # Parents the control under the follicle
        cmds.parent(control_group, follicle_transform)
        cmds.setAttr(f"{follicle}.visibility", 0)

    # Sets up the closest point constraint for getting the joint positions in the loop
    cmds.select(nurbs_surface)
    cmds.ClosestPointOn()
    closest_point_constraint = cmds.ls(type="closestPointOnSurface")[-1]
    closest_point_locator = cmds.listConnections(
        f"{closest_point_constraint}.inPosition"
    )
    max_v_range = cmds.getAttr(f"{nurbs_shape}.minMaxRangeV")[0][-1]

    # Empty list to store the new control joints
    control_joints = []

    # Creates the empty transforms above each duplicated joint
    for index, jnt in enumerate(selection):
        # Create new joint
        duplicated_joint = cmds.duplicate(
            jnt,
            name=name_object(node_name=f"0{index+1}_ctrl_jnt"),
            parentOnly=True,
        )[0]
        # Add the new joint to the control_joints list
        control_joints.append(duplicated_joint)

        # Creates joint position attribute to store joint position
        cmds.addAttr(duplicated_joint, longName="jointPosition")
        cmds.setAttr(f"{duplicated_joint}.jointPosition", keyable=True)

        # Places the closest point constraint locators at each joint
        # and normalizes the V value to get the joint position
        joint_position = cmds.xform(
            duplicated_joint, query=True, matrix=True, worldSpace=True
        )
        cmds.xform(closest_point_locator, matrix=joint_position, worldSpace=True)
        current_joint_v_position = cmds.getAttr(f"{closest_point_constraint}.parameterV")
        normalized_joint_v_position = current_joint_v_position / max_v_range
        # Sets the jointPosition attribute on the joint as the normalized joint position
        # relative to the nurbs surface
        cmds.setAttr(f"{duplicated_joint}.jointPosition", normalized_joint_v_position)

        # Maya returns error if the object is already parented to the world
        try:
            cmds.parent(duplicated_joint, world=True)
        except:
            pass

        cmds.select(duplicated_joint)
        # Creates x amount of empty transforms above each ctrl joint,
        # depending on the number of controls
        joint_offset_groups = [
            create_offset_group(
                name=f"0{index+1}_ctrl_jnt_0{ctrl}_offset_grp",
                target=duplicated_joint
            )
            for ctrl in range(1, number_of_controls+1)
        ]

        # Creates a main offset group to catch any translations and rotations
        joint_parent_offset_group = create_offset_group(
            name=f"0{index+1}_ctrl_jnt_main_offset_grp", target=joint_offset_groups[0]
        )

        # One iteration behind the loop, to get the parent
        duplicated_joint_parent = name_object(node_name=f"0{index}_ctrl_jnt")
        if cmds.objExists(duplicated_joint_parent):
            cmds.parent(joint_parent_offset_group, duplicated_joint_parent)


        # ----------------------------------------------------------------------------------
        # Builds the logic and connections for the variable FK
        for index, joint_offset_group in enumerate(joint_offset_groups):
            # Defines a base name for all the nodes in the loop
            # ctrl[1] is the group and ctrl[0] is the curve
            starter_node_name = lambda node_name: name_object(
                name=joint_offset_group, node_name=node_name, include_system_name=False
            )
            current_control = control_groups[index][0]

            # Creates both falloff positions for behind and infront of the control
            falloff_rear_position = create_node(
                type="plusMinusAverage",
                name=starter_node_name("ctrlpos_minus_falloff_pma"),
                set_attrs=[("*.operation", 2)],
                connect_attrs=[(f"{current_control}.position", "*.input1D[0]"),
                    (f"{current_control}.falloff", "*.input1D[1]")
                ],
            )
            falloff_front_position = create_node(
                type="plusMinusAverage",
                name=starter_node_name("ctrlpos_plus_falloff_pma"),
                connect_attrs=[(f"{current_control}.position", "*.input1D[0]"),
                    (f"{current_control}.falloff", "*.input1D[1]")
                ],
            )

            # Creates the rotation multiplier for later
            # Will be responsible for dividing the jnt pos minus the falloff pos by
            # the control position minus the falloff position
            rotation_multiplier = create_node(
                type="multiplyDivide",
                name=starter_node_name(f"rotation_multiplier_multi"),
                set_attrs=[("*.operation", 2)],
            )

            # Builds parallel networks for both sides

            for falloff_position in [falloff_rear_position, falloff_front_position]:
                if falloff_position in falloff_rear_position:
                    current_side = "rear"
                    multi_attr = "X"
                else:
                    current_side = "front"
                    multi_attr = "Y"

                # Joint position minus the falloff position
                jnt_pos_minus_falloff_pos = create_node(
                    type="plusMinusAverage",
                    name=starter_node_name(f"jntpos_minus_{current_side}_falloff_pma"),
                    connect_attrs=[
                        (f"{duplicated_joint}.jointPosition", "*.input1D[0]"),
                        (f"{falloff_position}.output1D", "*.input1D[1]"),
                        (f"*.output1D", f"{rotation_multiplier}.input1{multi_attr}"),
                    ],
                    set_attrs=[("*.operation", 2)]
                )
                # Control position minus the falloff position
                ctrl_pos_minus_falloff_pos = create_node(
                    type="plusMinusAverage",
                    name=starter_node_name(f"ctrlpos_minus_{current_side}_falloff_pma"),
                    connect_attrs=[
                        (f"{current_control}.position", "*.input1D[0]"),
                        (f"{falloff_position}.output1D", "*.input1D[1]"),
                        (f"*.output1D", f"{rotation_multiplier}.input2{multi_attr}"),
                    ],
                    set_attrs=[("*.operation", 2)]
                )

            # Condition uses the jnt - falloff if the control pos is greater than the joint
            # If the control pos is less than the joint pos it uses the jnt + falloff network
            side_switch_condition = create_node(
                type="condition",
                name=starter_node_name("side_switch_condition"),
                connect_attrs=[
                    (f"{current_control}.position", "*.firstTerm"),
                    (f"{duplicated_joint}.jointPosition", "*.secondTerm"),
                    (f"{rotation_multiplier}.outputX", f"*.colorIfTrueR"),
                    (f"{rotation_multiplier}.outputY", f"*.colorIfFalseR"),
                ],
                set_attrs=[("*.operation", 3)] # 3 == Greater than, 5 less than
            )

            # Multiplies the new multiplier value from the condition with the rotation of the control
            multiply_node_attributes = lambda source_attr: [
                (source_attr, f"*.input1{channel}")
                for channel in ["X", "Y", "Z"]]

            control_rotation_by_rot_multi = create_node(
                type="multiplyDivide",
                name=starter_node_name("rot_mult_by_ctrl_rot_multi"),
                connect_attrs=[
                    *multiply_node_attributes(f"{side_switch_condition}.outColorR"),
                    (f"{current_control}.rotate", "*.input2")],
            )


            # Takes 1 divided by the number of joints effected
            number_of_joints_division_multi = create_node(
                type="multiplyDivide",
                name=starter_node_name("num_of_jnts_div_multi"),
                connect_attrs=[(f"{current_control}.numOfJointsEffected", "*.input2X")],
                set_attrs=[("*.operation", 2), ("*.input1X", 1)],
            )
            # Multiplying the result from 'number_of_joints_division_multi' by 'control_rotation_by_rot_multi'
            num_jnts_times_ctrl_rot_multi = create_node(
                type="multiplyDivide",
                name=starter_node_name("num_jnts_times_ctrl_rot_multi"),
                connect_attrs=[
                    *multiply_node_attributes(f"{number_of_joints_division_multi}.outputX"),
                    (f"{control_rotation_by_rot_multi}.output", "*.input2")],
            )
            # Multiplies by 2
            final_multiplier_multi = create_node(
                type="multiplyDivide",
                name=starter_node_name("final_multi"),
                connect_attrs=[(f"{num_jnts_times_ctrl_rot_multi}.output", "*.input1")],
                set_attrs=[(f"*.input2{channel}", 6) for channel in ["X", "Y", "Z"]]
            )


            final_condition = create_node(
                type="condition",
                name=starter_node_name("final_condition"),
                connect_attrs=[
                    (f"{final_multiplier_multi}.output", "*.colorIfTrue"),
                    (f"{side_switch_condition}.outColorR", "*.firstTerm"),
                ],
                set_attrs=[("*.operation", 2)] + [
                    (f"*.colorIfFalse{channel}", 0) for channel in ["R","G","B"]
                ],
            )


            # Connects the system to the control transforms
            cmds.connectAttr(f"{final_condition}.outColor", f"{joint_offset_group}.rotate")

    # Removes the closest point constraint and it's locators
    closest_point_second_locator = cmds.listConnections(f"{closest_point_constraint}.position")
    cmds.delete(
        closest_point_constraint, closest_point_second_locator, closest_point_locator
    )

    # Gets all the joint positions from the ctrl joints
    joint_positions = [cmds.getAttr(f"{jnt}.jointPosition") for jnt in control_joints]

    # Orients controls to the closest joints
    for ctrl in control_groups:
        # Gets the control position
        ctrl_position = cmds.getAttr(f"{ctrl[0]}.position")
        # Finds the closest joint position
        closest_joint_position = min(
            joint_positions,
            key=lambda current_joint_position: abs(
                current_joint_position - ctrl_position
            ),
        )
        # Grabs the closest joint from the control_joints list
        closest_joint = control_joints[joint_positions.index(closest_joint_position)]
        # Orients the control group
        closest_joint_orientation = cmds.xform(
            closest_joint, query=True, rotation=True, worldSpace=True
        )
        cmds.xform(ctrl[1], rotation=closest_joint_orientation, worldSpace=True)

    # Binds the new joints to the nurbs surface
    nurbs_surface_cluster = cmds.skinCluster(control_joints, nurbs_surface)[0]
    # Connects the controls joints back to the bind joints
    bind_joint_constraints = [
        cmds.parentConstraint(ctrl_jnt, bind_jnt, maintainOffset=False) 
        for bind_jnt, ctrl_jnt in zip(selection, control_joints)
    ]
    
    MGlobal.displayInfo("\\\ Created Variable FK System")

if __name__ == "__main__":
	# Run the function
    build_variable_fk(
    	number_of_controls=3, 
    	control_normal=[1,0,0], 
    	control_size=22
    )