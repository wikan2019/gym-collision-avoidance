import numpy as np
import os
import operator
from gym_collision_avoidance.envs.policies.Policy import Policy
from gym_collision_avoidance.envs import util
from gym_collision_avoidance.envs.config import Config

from gym_collision_avoidance.envs.policies.DRL_Long.model.ppo import generate_action_no_sampling
from gym_collision_avoidance.envs.policies.DRL_Long.model.net import MLPPolicy, CNNPolicy

import torch
import torch.nn as nn
from collections import deque

MAX_EPISODES = 5000
LASER_BEAM = 512
LASER_HIST = 3
HORIZON = 200
GAMMA = 0.99
LAMDA = 0.95
BATCH_SIZE = 512
EPOCH = 3
COEFF_ENTROPY = 5e-4
CLIP_VALUE = 0.1
NUM_ENV = 50
OBS_SIZE = 512
ACT_SIZE = 2
LEARNING_RATE = 5e-5


class DRLLongPolicy(Policy):
    def __init__(self):
        Policy.__init__(self, str="DRL_Long")
        self.is_still_learning = False
        self.obs_stack = None

    def initialize_network(self, **kwargs):
        if 'checkpt_name' in kwargs:
            checkpt_name = kwargs['checkpt_name']
        else:
            checkpt_name = 'stage2.pth'

        if 'checkpt_dir' in kwargs:
            checkpt_dir = os.path.dirname(os.path.realpath(__file__)) + '/DRL_Long/policy/' + kwargs['checkpt_dir'] +'/'
        else:
            checkpt_dir = os.path.dirname(os.path.realpath(__file__)) + '/DRL_Long/policy/'

        policy_path = checkpt_dir + checkpt_name

        policy = CNNPolicy(frames=LASER_HIST, action_space=2)

        if os.path.exists(policy_path):
            # print('Loading DRL_Long policy...')
            state_dict = torch.load(policy_path, map_location=torch.device('cpu'))
            policy.load_state_dict(state_dict)
        else:
            print ('Error: Policy File Cannot Find')
            exit()

        self.nn = policy
        self.action_bound = [[0, -1], [1, 1]]

    def find_next_action(self, obs, agents, i):
        host_agent = agents[i]
        other_agents = agents[:i]+agents[i+1:]

        laserscan = obs['laserscan'] / 6.0 - 0.5

        x, y = host_agent.pos_global_frame
        goal_x, goal_y = host_agent.goal_global_frame
        theta = host_agent.heading_global_frame
        local_x = (goal_x - x) * np.cos(theta) + (goal_y - y) * np.sin(theta)
        local_y = -(goal_x - x) * np.sin(theta) + (goal_y - y) * np.cos(theta)
        goal = [local_x, local_y]

        # speed: [v.linear.x, v.angular.z]
        speed = host_agent.vel_global_frame[0]*np.array([np.cos(host_agent.heading_global_frame), np.sin(host_agent.heading_global_frame)])
        if self.obs_stack is None:
            self.obs_stack = deque([laserscan, laserscan, laserscan])
        else:
            self.obs_stack.popleft()
            self.obs_stack.append(laserscan)

        state = [self.obs_stack, goal, speed]
        state_list = [state]

        mean, scaled_action = generate_action_no_sampling(env=None, state_list=state_list,
                                               policy=self.nn, action_bound=self.action_bound)

        [vx, vw] = scaled_action[0]
        delta_heading = vw*Config.DT
        action = np.array([vx, delta_heading])

        # TODO: Account for pref_speed??????

        # action = np.array([host_agent.pref_speed*raw_action[0], raw_action[1]])
        return action