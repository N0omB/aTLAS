from channels.generic.websocket import AsyncJsonWebsocketConsumer
import json
import trustlab.lab.config as config
import time
from trustlab.models import *
from trustlab.serializers.scenario_serializer import ScenarioSerializer
from trustlab.lab.director import Director


class LabConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

    async def disconnect(self, close_code):
        pass

    async def receive_json(self, content, **kwargs):
        if content['type'] == 'run_scenario':
            serializer = ScenarioSerializer(data=content['scenario'])
            if serializer.is_valid():
                try:
                    scenario_factory = ScenarioFactory()
                    scenario = serializer.create(serializer.data)
                except ValueError as value_error:
                    await self.send_json({
                        'message': str(value_error),
                        'type': 'error'
                    })
                    return
                if scenario not in scenario_factory.scenarios:
                    scenario_factory.scenarios.append(scenario)
                director = Director(scenario)
                try:
                    async with config.PREPARE_SCENARIO_SEMAPHORE:
                        if config.TIME_MEASURE:
                            preparation_start_timer = time.time()
                        await director.prepare_scenario()
                    await self.send_json({
                        'scenario_run_id': director.scenario_run_id,
                        'type': "scenario_run_id"
                    })
                    if config.TIME_MEASURE:
                        preparation_end_timer = time.time()
                        print(f"Preparation took {preparation_end_timer - preparation_start_timer} s")
                        execution_start_timer = time.time()
                    trust_log, agent_trust_logs = await director.run_scenario()
                    if config.TIME_MEASURE:
                        execution_end_timer = time.time()
                        # noinspection PyUnboundLocalVariable
                        print(f"Execution took {execution_end_timer - execution_start_timer} s")
                        cleanup_start_timer = time.time()
                    await director.end_scenario()
                    if config.TIME_MEASURE:
                        cleanup_end_timer = time.time()
                        # noinspection PyUnboundLocalVariable
                        print(f"CleanUp took {cleanup_end_timer - cleanup_start_timer} s")
                    for agent in agent_trust_logs:
                        agent_trust_logs[agent] = "".join(agent_trust_logs[agent])
                    await self.send_json({
                            'agents_log': json.dumps(agent_trust_logs),
                            'trust_log': "".join(trust_log),
                            'scenario_run_id': director.scenario_run_id,
                            'type': "scenario_results"
                        })
                except Exception as exception:
                    await self.send_json({
                        'message': str(exception),
                        'type': 'error'
                    })
            else:
                await self.send(text_data=json.dumps({
                    'message': serializer.errors,
                    'type': 'error'
                }))
        elif content['type'] == 'get_scenario_results':
            result_factory = ResultFactory()
            current_id = content['scenario_run_id']
            if config.validate_scenario_run_id(current_id):
                try:
                    scenario_result = result_factory.get_result(current_id)
                    await self.send_json({
                        'agents_log': json.dumps(scenario_result.agent_trust_logs),
                        'trust_log': "".join(scenario_result.trust_log),
                        'scenario_run_id': scenario_result.scenario_run_id,
                        'type': "scenario_results"
                    })
                except OSError as exception:
                    await self.send_json({
                        'message': "Scenario Result not found",
                        'exception': str(exception),
                        'type': 'scenario_result_error'
                    })
            else:
                await self.send_json({
                    'message': "Scenario Run ID is not valid",
                    'type': 'scenario_result_error'
                })




