# -*- coding: utf-8 -*-
"""
This enables to parameterize the nodes that participate to the simulated federated learning scenario.
"""

import keras
import numpy as np
from random import shuffle

import utils
import constants

class Node:
    def __init__(self, x_train, x_test, y_train, y_test, node_id):
        self.x_train = x_train
        self.x_val = []
        self.x_test = x_test

        self.y_train = y_train
        self.y_val = []
        self.y_test = y_test

        self.node_id = node_id

    def get_x_train_len(self):
        return len(self.x_train)

    def preprocess_data(self):
        self.x_train = utils.preprocess_input(self.x_train)
        self.x_test = utils.preprocess_input(self.x_test)

        # Preprocess labels (y) data
        self.y_train = keras.utils.to_categorical(self.y_train, constants.NUM_CLASSES)
        self.y_test = keras.utils.to_categorical(self.y_test, constants.NUM_CLASSES)

    def corrupt_labels(self):
        for label in self.y_train:
            idx_max = np.argmax(label)
            label[idx_max] = 0.0
            label[idx_max - 1] = 1.0

    def shuffle_labels(self):
        for label in self.y_train:
            label = shuffle(label)
