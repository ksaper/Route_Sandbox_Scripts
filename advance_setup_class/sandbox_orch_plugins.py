from cloudshell.workflow.orchestration.sandbox import Sandbox
from cloudshell.api.cloudshell_api import InputNameValue, ResourceCommandListInfo
from collections import OrderedDict


class ResourceCommandHelper(object):
    def __init__(self, command_name='', device_name='', device_family='', device_model='', run_type='enqueue',
                 inputs={}):
        """

        :param string command_name: Name of the Command on the Resource to Run
        :param string device_family: The Name of the Device Family for lookup to run against (validation)
        :param string device_model: The Name of the Device Model for lookup to run against (validation)
        :param string device_name: The Name of the Exact Device to run against (validation)
        :param string run_type: enqueue or execute - how to run the command (fire & forget vs wait to complete)
                                *Connected Commands can only Execute
        :param OrderedDict inputs: Key == Input Name, Value == Input Value
        """
        self.name = command_name
        self.device_name = device_name.upper()
        self.family_name = device_family.upper()
        self.model_name = device_model.upper()
        self.run_type = run_type.upper()
        self.parameters = inputs


class ServiceCommandHelper(object):
    def __init__(self, command_name='', service_name='', run_type='enqueue', inputs={}):
        """

        :param string command_name: Name of the Command on the Service to Run
        :param string service_name: Name of the Service to Use
        :param string run_type: Enqueue or Execute this command (fire and forget vs wait to complete)
        :param OrderedDict inputs: Key == Input Name, Value == Input Value
        """
        self.name = command_name
        self.service_name = service_name
        self.run_type = run_type.upper()
        self.parameters = inputs


class SandboxOrchPlugins(object):
    def __init__(self):
        pass

    def _build_cmd_list_from_cmdlistinfo(self, command_list):
        """

        :param ResourceCommandListInfo command_list:
        :return: List commands:
        """
        commands = []
        for each in command_list:
            commands.append(each.Name)

        return commands

    def connect_all_routes(self, sandbox, components):
        """
        examines the routes listed for the sandbox being activated, and creates two lists of routes to be created
        (bi & uni-directional).  Lists passed into the ConnectRoutesInReservation are just paired endpoints
        in an open list:
        ['source1', 'target1', 'source2', 'target2', ... 'sourceN', 'targetN']
        :param Sandbox sandbox: Sandbox context obj
        :param TopologiesRouteInfo components:  List of Route Objects found in the reservation being used
        :return: Bool result: If Command Called
        """
        result = False
        w2output = sandbox.automation_api.WriteMessageToReservationOutput
        bi_routes = []
        uni_routes = []
        for route in components:
            for r in route:
                if r.RouteType == 'bi':
                    bi_routes.append(r.Source)
                    bi_routes.append(r.Target)
                elif r.RouteType == 'uni':
                    uni_routes.append(r.Source)
                    uni_routes.append(r.Target)

        # set Bi-Dir Routes:
        if len(bi_routes) > 0:
            try:
                w2output(sandbox.id,
                         'Queueing {} Bi-Dir Routes for Connection'.format(len(bi_routes) / 2))
                sandbox.automation_api.ConnectRoutesInReservation(reservationId=sandbox.id,
                                                                  endpoints=bi_routes,
                                                                  mappingType='bi')
                result = True
            except Exception as err:
                w2output(sandbox.id, err.message)

        if len(uni_routes) > 0:
            try:
                w2output(sandbox.id,
                         'Queueing {} Uni-Dir Routes for Connection'.format(len(uni_routes) / 2))
                sandbox.automation_api.ConnectRoutesInReservation(reservationId=sandbox.id,
                                                                  endpoints=uni_routes,
                                                                  mappingType='uni')
                result = True
            except Exception as err:
                w2output(sandbox.id, err.message)

        return result

    def disconnect_all_routes(self, sandbox, components):
        """
        examines the all routes listed in the sandbox being, and creates a list of routes to be disconnected
        Lists passed into the ConnectRoutesInReservation are just paired endpoints
        in an open list:
        ['source1', 'target1', 'source2', 'target2', ... 'sourceN', 'targetN']
        :param Sandbox sandbox: Sandbox context obj
        :param TopologiesRouteInfo components:  List of Route Objects found in the reservation being used
        :return: Bool result: If Command Called
        """
        result = False
        w2output = sandbox.automation_api.WriteMessageToReservationOutput
        routes = []
        for route in components:
            for r in route:
                routes.append(r.Source)
                routes.append(r.Target)

        if len(routes) > 0:
            try:
                ('Queueing {} Routes for disconnection'.format(len(routes) / 2))
                sandbox.automation_api.DisconnectRoutesInReservation(reservationId=sandbox.id,
                                                                     endpoints=routes)
                result = True
            except Exception as err:
                w2output(reservationId=sandbox.id, message=err.message)

        return result

    def run_resource_command_on_all(self, sandbox, components):
        """
        designed to call a singular command on all devices, such as a Power Up.
        Verifies first that the command exists, and then launches it.
        Execute vs. Enqueue - Execute waits for it to complete
        :param Sandbox sandbox:
        :param ResourceCommandHelper components: Use the CommandHelper (ignores Family & Model)
        :return: Bool result: If command was called
        """
        result = False

        if components.name == '':  # if the command is blank, stop here
            return result

        devices = sandbox.components.resources
        reg_commands = []  # commands as part of the Shell/Driver
        con_commands = []  # commands inherited via connection (Power)

        for device in devices:
            reg_cmd_check = False

            reg_commands = self._build_cmd_list_from_cmdlistinfo(
                sandbox.automation_api.GetResourceCommands(device).Commands)

            con_commands = self._build_cmd_list_from_cmdlistinfo(
                sandbox.automation_api.GetResourceConnectedCommands(device).Commands)

            if len(reg_commands) > 0:
                if components.name in reg_commands:
                    reg_cmd_check = True
                    params = []
                    for key in components.parameters.keys():
                        params.append(InputNameValue(key, components.parameters[key]))

                    try:
                        if components.run_type == 'EXECUTE':
                            sandbox.automation_api.ExecuteCommand(reservationId=sandbox.id,
                                                                  targetName=device,
                                                                  targetType='Resource',
                                                                  commandName=components.name,
                                                                  commandInputs=params)
                            result = True
                        elif components.run_type == 'ENQUEUE':
                            sandbox.automation_api.EnqueueCommand(reservationId=sandbox.id,
                                                                  targetName=device,
                                                                  targetType='Resource',
                                                                  commandName=components.name,
                                                                  commandInputs=params)
                            result = True
                    except Exception as err:
                        sandbox.automation_api.WriteMessageToReservationOutput(reservationId=sandbox.id,
                                                                               message=err.message)

            if len(con_commands) > 0 and not reg_cmd_check:
                if components.name in con_commands:
                    try:
                        params = []
                        for key in components.parameters.keys():
                            params.append(InputNameValue(key, components.parameters[key]))

                        sandbox.automation_api.ExecuteResourceConnectedCommand(reservationId=sandbox.id,
                                                                               resourceFullPath=device,
                                                                               commandName=components.name,
                                                                               parameterValues=params)
                        result = True
                    except Exception as err:
                        sandbox.automation_api.WriteMessageToReservationOutput(reservationId=sandbox.id,
                                                                               message=err.message)

        return result

    def run_resource_command_on_select(self, sandbox, components):
        """

        :param Sandbox sandbox:
        :param ResourceCommandHelper components:
        :return: Bool result: If a command was called
        """
        result = False

        if components.name == '':  # if the command is blank, stop here
            return result

        devices = sandbox.components.resources

        for device in devices:
            reg_commands = []  # commands as part of the Shell/Driver
            con_commands = []  # commands inherited via connection (Power)
            reg_cmd_check = False
            resource = sandbox.automation_api.GetResourceDetails(device)

            if components.device_name == device.upper():

                reg_commands = self._build_cmd_list_from_cmdlistinfo(
                    sandbox.automation_api.GetResourceCommands(device).Commands)

                con_commands = self._build_cmd_list_from_cmdlistinfo(
                    sandbox.automation_api.GetResourceConnectedCommands(device).Commands)

            elif components.family_name == resource.ResourceFamilyName.upper() and \
                    components.model_name == resource.ResourceModelName.upper() and components.device_name == '':

                reg_commands = self._build_cmd_list_from_cmdlistinfo(
                    sandbox.automation_api.GetResourceCommands(device).Commands)

                con_commands = self._build_cmd_list_from_cmdlistinfo(
                    sandbox.automation_api.GetResourceConnectedCommands(device).Commands)

            elif components.model_name == resource.ResourceModelName.upper() and \
                    components.family_name == '' and components.device_name == '':

                reg_commands = self._build_cmd_list_from_cmdlistinfo(
                    sandbox.automation_api.GetResourceCommands(device).Commands)

                con_commands = self._build_cmd_list_from_cmdlistinfo(
                    sandbox.automation_api.GetResourceConnectedCommands(device).Commands)

            elif components.family_name == resource.ResourceFamilyName.upper() and \
                    components.model_name == '' and components.device_name == '':

                reg_commands = self._build_cmd_list_from_cmdlistinfo(
                    sandbox.automation_api.GetResourceCommands(device).Commands)

                con_commands = self._build_cmd_list_from_cmdlistinfo(
                    sandbox.automation_api.GetResourceConnectedCommands(device).Commands)

            if len(reg_commands) > 0:
                if components.name in reg_commands:
                    reg_cmd_check = True
                    params = []
                    for key in components.parameters.keys():
                        params.append(InputNameValue(key, components.parameters[key]))

                    try:
                        if components.run_type == 'EXECUTE':
                            sandbox.automation_api.ExecuteCommand(reservationId=sandbox.id,
                                                                  targetName=device,
                                                                  targetType='Resource',
                                                                  commandName=components.name,
                                                                  commandInputs=params)
                            result = True
                        elif components.run_type == 'ENQUEUE':
                            sandbox.automation_api.EnqueueCommand(reservationId=sandbox.id,
                                                                  targetName=device,
                                                                  targetType='Resource',
                                                                  commandName=components.name,
                                                                  commandInputs=params)
                            result = True
                    except Exception as err:
                        sandbox.automation_api.WriteMessageToReservationOutput(reservationId=sandbox.id,
                                                                               message=err.message)

            if len(con_commands) > 0 and not reg_cmd_check:
                if components.name in con_commands:
                    try:
                        params = []
                        for key in components.parameters.keys():
                            params.append(InputNameValue(key, components.parameters[key]))

                        sandbox.automation_api.ExecuteResourceConnectedCommand(reservationId=sandbox.id,
                                                                               resourceFullPath=device,
                                                                               commandName=components.name,
                                                                               parameterValues=params)
                        result = True
                    except Exception as err:
                        sandbox.automation_api.WriteMessageToReservationOutput(reservationId=sandbox.id,
                                                                               message=err.message)

        return result