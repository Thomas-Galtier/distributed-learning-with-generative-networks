# -*- coding: utf-8 -*-
"""
This enables to parameterize the contributivity measurements to be performed.
"""

from __future__ import print_function

import datetime
from timeit import default_timer as timer
import numpy as np
from scipy.stats import norm
from itertools import combinations
from math import factorial
from sklearn.linear_model import LinearRegression
from scipy.special import softmax

import fl_training
import shapley_value.shapley as sv


class krigingModel:
    def __init__(self, degre, covariance_func):
        self.X = np.array([[]])
        self.Y = np.array([[]])
        self.cov_f = covariance_func
        self.degre = degre
        self.beta = np.array([[]])
        self.H = np.array([[]])
        self.K = np.array([[]])
        self.invK = np.array([[]])

    def fit(self, X, Y):
        self.X = X
        self.Y = Y
        K = np.zeros((len(X), len(X)))
        H = np.zeros((len(X), self.degre + 1))
        for i, d in enumerate(X):
            for j, b in enumerate(X):
                K[i, j] = self.cov_f(d, b)
            for j in range(self.degre + 1):
                H[i, j] = np.sum(d) ** j
        self.H = H
        self.K = np.linalg.inv(K)
        self.invK = np.linalg.inv(K)
        Ht_invK_H = H.transpose().dot(self.invK).dot(H)
        self.beta = (
            np.linalg.inv(Ht_invK_H).dot(H.transpose()).dot(self.invK).dot(self.Y)
        )

    def predict(self, x):
        gx = []
        for i in range(self.degre + 1):
            gx.append(np.sum(x) ** i)
        gx = np.array(gx)
        cx = []
        for i in range(len(self.X)):
            cx.append([self.cov_f(self.X[i], x)])
        cx = np.array(cx)
        pred = gx.transpose().dot(self.beta) + cx.transpose().dot(self.invK).dot(
            self.Y - self.H.dot(self.beta)
        )
        return pred


class Contributivity:
    def __init__(self, name="", scenario=None):
        self.name = name
        n = len(scenario.node_list)
        self.contributivity_scores = np.zeros(n)
        self.scores_std = np.zeros(n)
        self.normalized_scores = np.zeros(n)
        self.computation_time = 0.0
        self.charac_fct_calls_count = 0
        self.charac_fct_values = {(): 0}
        self.increments_values = []
        for i in range(n):
            self.increments_values.append(dict())

    def __str__(self):
        computation_time = str(datetime.timedelta(seconds=self.computation_time))
        output = "\n" + self.name + "\n"
        output += "Computation time: " + computation_time + "\n"
        output += (
            "Number of characteristic function computed: "
            + str(self.charac_fct_calls_count)
            + "\n"
        )
        # TODO print only 3 digits
        output += "Contributivity scores: " + str(self.contributivity_scores) + "\n"
        output += "Std of the contributivity scores: " + str(self.scores_std) + "\n"
        output += (
            "Normalized contributivity scores: " + str(self.normalized_scores) + "\n"
        )

        return output

    def not_twice_characteristic(self, subset, the_scenario):

        if len(subset) > 0:
            subset = np.sort(subset)
        if (
            tuple(subset) not in self.charac_fct_values
        ):  # Characteristic_func(permut) has not been computed yet, so we compute, store, and return characteristic_func(permut)
            self.charac_fct_calls_count += 1
            small_node_list = np.array([the_scenario.node_list[i] for i in subset])
            self.charac_fct_values[tuple(subset)] = fl_training.compute_test_score(
                small_node_list,
                the_scenario.epoch_count,
                the_scenario.x_val,
                the_scenario.y_val,
                the_scenario.x_test,
                the_scenario.y_test,
                the_scenario.aggregation_weighting,
                the_scenario.minibatch_count,
                the_scenario.is_early_stopping,
                save_folder=the_scenario.save_folder,
            )
            # we add the new increments
            for i in range(len(the_scenario.node_list)):
                if i in subset:
                    subset_without_i = np.delete(subset, np.argwhere(subset == i))
                    if (
                        tuple(subset_without_i) in self.charac_fct_values
                    ):  # we store the new knwon increments
                        self.increments_values[i][tuple(subset_without_i)] = (
                            self.charac_fct_values[tuple(subset)]
                            - self.charac_fct_values[tuple(subset_without_i)]
                        )
                else:
                    subset_with_i = np.sort(np.append(subset, i))
                    if (
                        tuple(subset_with_i) in self.charac_fct_values
                    ):  # we store the new knwon increments
                        self.increments_values[i][tuple(subset)] = (
                            self.charac_fct_values[tuple(subset_with_i)]
                            - self.charac_fct_values[tuple(subset)]
                        )
        # else we will Return the characteristic_func(permut) that was already computed
        return self.charac_fct_values[tuple(subset)]

    # %% Generalization of Shapley Value computation

    def compute_SV(self, the_scenario):
        start = timer()
        print("\n# Launching computation of Shapley Value of all nodes")

        self.charac_fct_calls_count += 1
        # Initialize list of all players (nodes) indexes
        nodes_count = len(the_scenario.node_list)
        nodes_idx = np.arange(nodes_count)
        # print('All players (nodes) indexes: ', nodes_idx) # VERBOSE

        # Define all possible coalitions of players
        coalitions = [
            list(j)
            for i in range(len(nodes_idx))
            for j in combinations(nodes_idx, i + 1)
        ]
        # print('All possible coalitions of players (nodes): ', coalitions) # VERBOSE

        # For each coalition, obtain value of characteristic function...
        # ... i.e.: train and evaluate model on nodes part of the given coalition
        characteristic_function = []

        for coalition in coalitions:
            # print('\nComputing characteristic function on coalition ', coalition) # VERBOSE
            characteristic_function.append(
                self.not_twice_characteristic(coalition, the_scenario)
            )
        # print('\nValue of characteristic function for all coalitions: ', characteristic_function) # VERBOSE

        # Compute Shapley Value for each node
        # We are using this python implementation: https://github.com/susobhang70/shapley_value
        # It requires coalitions to be ordered - see README of https://github.com/susobhang70/shapley_value
        list_shapley_value = sv.main(nodes_count, characteristic_function)

        # Return SV of each node
        self.name = "Shapley values"
        self.contributivity_scores = np.array(list_shapley_value)
        self.scores_std = np.zeros(len(list_shapley_value))
        self.normalized_scores = list_shapley_value / np.sum(list_shapley_value)
        end = timer()
        self.computation_time = end - start

    # %% compute independent raw scores
    def compute_independent_scores_raws(self, the_scenario):
        start = timer()

        print(
            "\n# Launching computation of perf. scores of models trained independently on each node"
        )

        # Initialize a list of performance scores
        performance_scores = []

        # Train models independently on each node and append perf. score to list of perf. scores
        for i in range(len(the_scenario.node_list)):
            performance_scores.append(
                self.not_twice_characteristic(np.array([i]), the_scenario)
            )
        self.name = "Independant scores raw"
        self.contributivity_scores = np.array(performance_scores)
        self.scores_std = np.zeros(len(performance_scores))
        self.normalized_scores = performance_scores / np.sum(performance_scores)
        end = timer()
        self.computation_time = end - start

    # %% compute independent additive scores

    def compute_independent_scores_additive(self, the_scenario):
        start = timer()

        collaborative_score = self.not_twice_characteristic(
            np.arange(len(the_scenario.node_list)), the_scenario
        )

        print(
            "\n# Launching computation of perf. scores of models trained independently on each node"
        )

        # Initialize a list of performance scores
        performance_scores = []

        # Train models independently on each node and append perf. score to list of perf. scores
        for i in range(len(the_scenario.node_list)):
            performance_scores.append(
                self.not_twice_characteristic(np.array([i]), the_scenario)
            )

        # Compute 'regularized' values of performance scores so that they are additive and their sum amount to the collaborative performance score obtained by the coalition of all players (nodes)
        perf_scores_additive = softmax(performance_scores) * collaborative_score

        self.name = "Independant scores additive"
        self.contributivity_scores = np.array(perf_scores_additive)
        self.scores_std = np.zeros(len(performance_scores))
        self.normalized_scores = perf_scores_additive / np.sum(perf_scores_additive)
        end = timer()
        self.computation_time = end - start

    # %% compute Shapley values with the truncated Monte-carlo metho

    def truncated_MC(self, the_scenario, sv_accuracy=0.01, alpha=0.9, truncation=0.05):
        """Return the vector of approximated Shapley value corresponding to a list of node and a characteristic function using the truncated monte-carlo method."""
        start = timer()
        n = len(the_scenario.node_list)

        characteristic_all_node = self.not_twice_characteristic(
            np.arange(n), the_scenario
        )  # Characteristic function on all nodes
        if n == 1:
            self.name = "TMC Shapley values"
            self.contributivity_scores = np.array([characteristic_all_node])
            self.scores_std = np.array([0])
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start
        else:
            contributions = np.array([[]])
            permutation = np.zeros(n)  # Store the current permutation
            t = 0
            q = norm.ppf((1 - alpha) / 2, loc=0, scale=1)
            v_max = 0
            while (
                t < 100 or t < q ** 2 * v_max / (sv_accuracy) ** 2
            ):  # Check if the length of the confidence interval  is below the value of sv_accuracy*characteristic_all_node
                t += 1

                if t == 1:
                    contributions = np.array([np.zeros(n)])
                else:
                    contributions = np.vstack((contributions, np.zeros(n)))

                permutation = np.random.permutation(n)  # Store the current permutation
                char_nodelists = np.zeros(
                    n + 1
                )  # Store the characteristic function on each ensemble built with the first elements of the permutation
                char_nodelists[-1] = characteristic_all_node
                for j in range(n):
                    # here we suppose the characteristic function is 0 for the empty set
                    if abs(characteristic_all_node - char_nodelists[j]) < truncation:
                        char_nodelists[j + 1] = char_nodelists[j]
                    else:
                        char_nodelists[j + 1] = self.not_twice_characteristic(
                            permutation[: j + 1], the_scenario
                        )
                    contributions[-1][permutation[j]] = (
                        char_nodelists[j + 1] - char_nodelists[j]
                    )
                v_max = np.max(np.var(contributions, axis=0))
            sv = np.mean(contributions, axis=0)
            self.name = "TMC Shapley values"
            self.contributivity_scores = sv
            self.scores_std = np.std(contributions, axis=0) / np.sqrt(t - 1)
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start

    # %% compute Shapley values with the truncated Monte-carlo method with a small bias correction

    def interpol_trunc_MC(
        self, the_scenario, sv_accuracy=0.01, alpha=0.9, truncation=0.05
    ):
        """Return the vector of approximated Shapley value corresponding to a list of node and a characteristic function using the interpolated truncated monte-carlo method."""
        start = timer()
        n = len(the_scenario.node_list)
        # Characteristic function on all nodes
        characteristic_all_node = self.not_twice_characteristic(
            np.arange(n), the_scenario
        )
        if n == 1:
            self.name = "ITMC Shapley values"
            self.contributivity_scores = np.array([characteristic_all_node])
            self.scores_std = np.array([0])
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start
        else:
            contributions = np.array([[]])
            permutation = np.zeros(n)  # Store the current permutation
            t = 0
            q = norm.ppf((1 - alpha) / 2, loc=0, scale=1)
            v_max = 0
            while (
                t < 100 or t < q ** 2 * v_max / (sv_accuracy) ** 2
            ):  # Check if the length of the confidence interval  is below the value of sv_accuracy*characteristic_all_node
                t += 1

                if t == 1:
                    contributions = np.array([np.zeros(n)])
                else:
                    contributions = np.vstack((contributions, np.zeros(n)))

                permutation = np.random.permutation(n)  # Store the current permutation
                char_nodelists = np.zeros(
                    n + 1
                )  # Store the characteristic function on each ensemble built with the first elements of the permutation
                char_nodelists[-1] = characteristic_all_node
                first = True
                for j in range(n):
                    # here we suppose the characteristic function is 0 for the empty set
                    if abs(characteristic_all_node - char_nodelists[j]) < truncation:
                        if first:
                            size_of_rest = 0
                            for i in range(j, n):
                                size_of_rest += len(the_scenario.node_list[i].y_train)
                            first = False
                        size_of_S = len(the_scenario.node_list[j].y_train)
                        char_nodelists[j + 1] = (
                            char_nodelists[j]
                            + size_of_S / size_of_rest * characteristic_all_node
                        )

                    else:
                        char_nodelists[j + 1] = self.not_twice_characteristic(
                            permutation[: j + 1], the_scenario
                        )
                    contributions[-1][permutation[j]] = (
                        char_nodelists[j + 1] - char_nodelists[j]
                    )
                v_max = np.max(np.var(contributions, axis=0))
            sv = np.mean(contributions, axis=0)
            self.name = "ITMC Shapley values"
            self.contributivity_scores = sv
            self.scores_std = np.std(contributions, axis=0) / np.sqrt(t - 1)
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start

    # # %% compute Shapley values with the importance sampling method

    def IS_lin(self, the_scenario, sv_accuracy=0.01, alpha=0.95):
        """Return the vector of approximated Shapley value corresponding to a list of node and a characteristic function using the importance sampling method and a linear interpolation model."""

        start = timer()
        n = len(the_scenario.node_list)
        # Characteristic function on all nodes
        characteristic_all_node = self.not_twice_characteristic(
            np.arange(n), the_scenario
        )
        if n == 1:
            self.name = "IS_lin Shapley values"
            self.contributivity_scores = np.array([characteristic_all_node])
            self.scores_std = np.array([0])
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start
        else:

            # definition of the original density
            def prob(subset):
                lS = len(subset)
                return factorial(n - 1 - lS) * factorial(lS) / factorial(n)

            # definition of the approximation of the increment
            # ## compute the last and the first increments in performance (they are needed to compute the approximated increments)
            characteristic_no_nodes = 0
            last_increments = []
            first_increments = []
            for k in range(n):
                last_increments.append(
                    characteristic_all_node
                    - self.not_twice_characteristic(
                        np.delete(np.arange(n), k), the_scenario
                    )
                )
                first_increments.append(
                    self.not_twice_characteristic(np.array([k]), the_scenario)
                    - characteristic_no_nodes
                )

            # ## definition of the number of data in all datasets
            size_of_I = 0
            for node in the_scenario.node_list:
                size_of_I += len(node.y_train)

            def approx_increment(subset, k):
                assert k not in subset, "" + str(k) + "is not in " + str(subset) + ""
                small_node_list = np.array([the_scenario.node_list[i] for i in subset])
                # compute the size of subset : ||subset||
                size_of_S = 0
                for node in small_node_list:
                    size_of_S += len(node.y_train)
                beta = size_of_S / size_of_I
                return (1 - beta) * first_increments[k] + beta * last_increments[k]

            # compute  the importance density
            # ## compute the renormalization constant of the importance density for all datatsets

            renorms = []
            for k in range(n):
                list_k = np.delete(np.arange(n), k)
                renorm = 0
                for length_combination in range(len(list_k) + 1):
                    for subset in combinations(
                        list_k, length_combination
                    ):  # could be avoided as   prob(np.array(subset))*np.abs(approx_increment(np.array(subset),j)) is constant in the combination
                        renorm += prob(np.array(subset)) * np.abs(
                            approx_increment(np.array(subset), k)
                        )
                renorms.append(renorm)

            # ## defines the importance density
            def g(subset, k):
                return (
                    prob(np.array(subset))
                    * np.abs(approx_increment(np.array(subset), k))
                    / renorms[k]
                )

            # sampling
            t = 0
            q = -norm.ppf((1 - alpha) / 2, loc=0, scale=1)
            v_max = 0
            while (
                t < 100 or t < 4 * q ** 2 * v_max / (sv_accuracy) ** 2
            ):  # Check if the length of the confidence interval  is below the value of sv_accuracy*characteristic_all_node
                t += 1
                if t == 1:
                    contributions = np.array([np.zeros(n)])
                else:
                    contributions = np.vstack((contributions, np.zeros(n)))
                for k in range(n):
                    u = np.random.uniform(0, 1, 1)[0]
                    cumSum = 0
                    list_k = np.delete(np.arange(n), k)
                    for length_combination in range(len(list_k) + 1):
                        for subset in combinations(
                            list_k, length_combination
                        ):  # could be avoided as   prob(np.array(subset))*np.abs(approx_increment(np.array(subset),j)) is constant in the combination
                            cumSum += prob(np.array(subset)) * np.abs(
                                approx_increment(np.array(subset), k)
                            )
                            if cumSum / renorms[k] > u:
                                S = np.array(subset)
                                break
                        if cumSum / renorms[k] > u:
                            break
                    SUk = np.append(S, k)
                    increment = self.not_twice_characteristic(
                        SUk, the_scenario
                    ) - self.not_twice_characteristic(S, the_scenario)
                    contributions[t - 1][k] = (
                        increment
                        * renorms[k]
                        / np.abs(approx_increment(np.array(S), k))
                    )
                v_max = np.max(np.var(contributions, axis=0))
            shap = np.mean(contributions, axis=0)
            self.name = "IS_lin Shapley values"
            self.contributivity_scores = shap
            self.scores_std = np.std(contributions, axis=0) / np.sqrt(t - 1)
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start

    # # %% compute Shapley values with the regression importance sampling method

    def IS_reg(self, the_scenario, sv_accuracy=0.01, alpha=0.95):
        """Return the vector of approximated Shapley value corresponding to a list of node and a characteristic function using the importance sampling method and a regression model."""
        start = timer()
        n = len(the_scenario.node_list)

        if n < 4:
            # Initialize list of all players (nodes) indexes
            nodes_count = len(the_scenario.node_list)
            nodes_idx = np.arange(nodes_count)

            # Define all possible coalitions of players
            coalitions = [
                list(j)
                for i in range(len(nodes_idx))
                for j in combinations(nodes_idx, i + 1)
            ]

            # For each coalition, obtain value of characteristic function...
            # ... i.e.: train and evaluate model on nodes part of the given coalition
            characteristic_function = []

            for coalition in coalitions:
                characteristic_function.append(
                    self.not_twice_characteristic(list(coalition), the_scenario)
                )
            # Compute exact Shapley Value for each node
            shap = sv.main(the_scenario.nodes_count, characteristic_function)
            self.name = "IS_reg Shapley values"
            self.contributivity_scores = shap
            self.scores_std = np.zeros(n)
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start
        else:

            # definition of the original density
            def prob(subset):
                lS = len(subset)
                return factorial(n - 1 - lS) * factorial(lS) / factorial(n)

            # definition of the approximation of the increment
            # ## compute some  increments
            permutation = np.random.permutation(n)
            for j in range(n):
                self.not_twice_characteristic(permutation[: j + 1])
            permutation = np.flip(permutation)
            for j in range(n):
                self.not_twice_characteristic(permutation[: j + 1])
            for k in range(n):
                permutation = np.append(permutation[-1], permutation[:-1])
                for j in range(n):
                    self.not_twice_characteristic(permutation[: j + 1])

            # ## do the regressions

            ###### make the datasets
            def makedata(subset):
                # compute the size of subset : ||subset||
                small_node_list = np.array([the_scenario.node_list[i] for i in subset])
                size_of_S = 0
                for node in small_node_list:
                    size_of_S += len(node.y_train)
                data = [size_of_S, size_of_S ** 2]
                return data

            datasets = []
            outputs = []
            for k in range(n):
                x = []
                y = []
                for subset, incr in self.increments_values[k].items():
                    x.append(makedata(subset))
                    y.append(incr)
                datasets.append(x)
                outputs.append(y)

            ###### fit the regressions
            models = []
            for k in range(n):
                model_k = LinearRegression()
                model_k.fit(datasets[k], outputs[k])
                models.append(model_k)

            # ##define the approximation
            def approx_increment(subset, k):
                return models[k].predict([makedata(subset)])[0]

            # compute  the importance density
            # ## compute the renormalization constant of the importance density for all datatsets

            renorms = []
            for k in range(n):
                list_k = np.delete(np.arange(n), k)
                renorm = 0
                for length_combination in range(len(list_k) + 1):
                    for subset in combinations(
                        list_k, length_combination
                    ):  # could be avoided as   prob(np.array(subset))*np.abs(approx_increment(np.array(subset),j)) is constant in the combination
                        renorm += prob(np.array(subset)) * np.abs(
                            approx_increment(np.array(subset), k)
                        )
                renorms.append(renorm)

            # sampling
            t = 0
            q = -norm.ppf((1 - alpha) / 2, loc=0, scale=1)
            v_max = 0
            while (
                t < 100 or t < 4 * q ** 2 * v_max / (sv_accuracy) ** 2
            ):  # Check if the length of the confidence interval  is below the value of sv_accuracy*characteristic_all_node
                t += 1
                if t == 1:
                    contributions = np.array([np.zeros(n)])
                else:
                    contributions = np.vstack((contributions, np.zeros(n)))
                for k in range(n):
                    u = np.random.uniform(0, 1, 1)[0]
                    cumSum = 0
                    list_k = np.delete(np.arange(n), k)
                    for length_combination in range(len(list_k) + 1):
                        for subset in combinations(
                            list_k, length_combination
                        ):  # could be avoided as   prob(np.array(subset))*np.abs(approx_increment(np.array(subset),j)) is constant in the combination
                            cumSum += prob(np.array(subset)) * np.abs(
                                approx_increment(np.array(subset), k)
                            )
                            if cumSum / renorms[k] > u:
                                S = np.array(subset)
                                break
                        if cumSum / renorms[k] > u:
                            break
                    SUk = np.append(S, k)
                    increment = self.not_twice_characteristic(
                        SUk, the_scenario
                    ) - self.not_twice_characteristic(S, the_scenario)
                    contributions[t - 1][k] = (
                        increment
                        * renorms[k]
                        / np.abs(approx_increment(np.array(S), k))
                    )
                v_max = np.max(np.var(contributions, axis=0))
            shap = np.mean(contributions, axis=0)
            self.name = "IS_reg Shapley values"
            self.contributivity_scores = shap
            self.scores_std = np.std(contributions, axis=0) / np.sqrt(t - 1)
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start

    # # %% compute Shapley values with the Kriging adaptive importance sampling method

    def AIS_Kriging(self, the_scenario, sv_accuracy=0.01, alpha=0.95, update=50):
        """Return the vector of approximated Shapley value corresponding to a list of node and a characteristic function using the importance sampling method and a Kriging model."""
        start = timer()

        n = len(the_scenario.node_list)

        # definition of the original density
        def prob(subset):
            lS = len(subset)
            return factorial(n - 1 - lS) * factorial(lS) / factorial(n)

        #     definition of the approximation of the increment
        ## compute some  increments to fuel the Kriging
        S = np.arange(n)
        self.not_twice_characteristic(S, the_scenario)
        for k1 in range(n):
            for k2 in range(n):
                S = np.array([k1])
                self.not_twice_characteristic(S, the_scenario)
                S = np.delete(np.arange(n), [k1])
                self.not_twice_characteristic(S, the_scenario)
                if k1 != k2:
                    S = np.array([k1, k2])
                    self.not_twice_characteristic(S, the_scenario)
                    S = np.delete(np.arange(n), [k1, k2])
                    self.not_twice_characteristic(S, the_scenario)

        # ## do the regressions

        def make_coordinate(subset, k):
            assert k not in subset
            # compute the size of subset : ||subset||
            coordinate = np.zeros(n)
            small_node_list = np.array([the_scenario.node_list[i] for i in subset])
            for node, i in zip(small_node_list, subset):
                coordinate[i] = len(node.y_train)
            coordinate = np.delete(coordinate, k)
            return coordinate

        def dist(x1, x2):
            return np.sqrt(np.sum((x1 - x2) ** 2))

        # make the covariance functions
        phi = np.zeros(n)
        cov = []
        for k in range(n):
            phi[k] = np.median(make_coordinate(np.delete(np.arange(n), k), k))

            def covk(x1, x2):
                return np.exp(-dist(x1, x2) ** 2 / phi[k] ** 2)

            cov.append(covk)

        def make_models():
            ###### make the datasets

            datasets = []
            outputs = []
            for k in range(n):
                x = []
                y = []
                for subset, incr in self.increments_values[k].items():
                    x.append(make_coordinate(subset, k))
                    y.append(incr)
                datasets.append(x)
                outputs.append(y)
            ###### fit the kriging
            models = []
            for k in range(n):
                model_k = krigingModel(2, cov[k])
                model_k.fit(datasets[k], outputs[k])
                models.append(model_k)
            all_models.append(models)

        # ##define the approximation
        def approx_increment(subset, k, j):
            return all_models[j][k].predict(make_coordinate(subset, k))[0]

        # sampling
        t = 0
        q = -norm.ppf((1 - alpha) / 2, loc=0, scale=1)
        v_max = 0
        all_renorms = []
        all_models = []
        Subsets = []  # created like this to avoid pointer issue
        while (
            t < 100 or t < 4 * q ** 2 * v_max / (sv_accuracy) ** 2
        ):  # Check if the length of the confidence interval  is below the value of sv_accuracy*characteristic_all_node
            if t == 0:
                contributions = np.array([np.zeros(n)])
            else:
                contributions = np.vstack((contributions, np.zeros(n)))
            subsets = []
            if t % update == 0:  # renew the importance density g
                j = t // update
                make_models()
                # ## compute the renormalization constant of the new importance density for all datatsets
                renorms = []
                for k in range(n):
                    list_k = np.delete(np.arange(n), k)
                    renorm = 0
                    for length_combination in range(len(list_k) + 1):
                        for subset in combinations(
                            list_k, length_combination
                        ):  # could be avoided as   prob(np.array(subset))*np.abs(approx_increment(np.array(subset),j)) is constant in the combination
                            renorm += prob(np.array(subset)) * np.abs(
                                approx_increment(np.array(subset), k, j)
                            )
                    renorms.append(renorm)
                all_renorms.append(renorms)

            # generate the new increments(subset)
            for k in range(n):
                u = np.random.uniform(0, 1, 1)[0]
                cumSum = 0
                list_k = np.delete(np.arange(n), k)
                for length_combination in range(len(list_k) + 1):
                    for subset in combinations(
                        list_k, length_combination
                    ):  # could be avoided as   prob(np.array(subset))*np.abs(approx_increment(np.array(subset),j)) is constant in the combination
                        cumSum += prob(np.array(subset)) * np.abs(
                            approx_increment(np.array(subset), k, j)
                        )
                        if cumSum / all_renorms[j][k] > u:
                            S = np.array(subset)
                            subsets.append(S)
                            break
                    if cumSum / all_renorms[j][k] > u:
                        break
                SUk = np.append(S, k)
                increment = self.not_twice_characteristic(
                    SUk, the_scenario
                ) - self.not_twice_characteristic(S, the_scenario)
                contributions[t - 1][k] = (
                    increment * all_renorms[j][k] / np.abs(approx_increment(S, k, j))
                )
            Subsets.append(subsets)
            shap = np.mean(contributions, axis=0)
            # calcul des variances
            v_max = np.max(np.var(contributions, axis=0))
            t += 1
            shap = np.mean(contributions, axis=0)
            self.name = "AIS Shapley values"
            self.contributivity_scores = shap
            self.scores_std = np.std(contributions, axis=0) / np.sqrt(t - 1)
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start

    # # %% compute Shapley values with the stratified sampling method

    def Stratified_MC(self, the_scenario, sv_accuracy=0.01, alpha=0.95):
        """Return the vector of approximated Shapley values using the stratified monte-carlo method."""

        start = timer()

        N = len(the_scenario.node_list)

        characteristic_all_node = self.not_twice_characteristic(
            np.arange(N), the_scenario
        )  # Characteristic function on all nodes

        if N == 1:
            self.name = "Stratified MC Shapley values"
            self.contributivity_scores = np.array([characteristic_all_node])
            self.scores_std = np.array([0])
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start
        else:
            # sampling
            gamma = 0.2
            beta = 0.0075
            t = 0
            sigma2 = np.zeros((N, N))
            mu = np.zeros((N, N))
            e = 0.0
            q = -norm.ppf((1 - alpha) / 2, loc=0, scale=1)
            v_max = 0
            continuer = []
            contributions = []
            for k in range(N):
                contributions.append(list())
                continuer.append(list())
            for k in range(N):
                for strata in range(N):
                    contributions[k].append(list())
                    continuer[k].append(True)
            while (
                np.any(continuer) or (sv_accuracy) ** 2 < 4 * q ** 2 * v_max
            ):  # Check if the length of the confidence interval  is below the value of sv_accuracy*characteristic_all_node
                t += 1
                e = (
                    1
                    + 1 / (1 + np.exp(gamma / beta))
                    - 1 / (1 + np.exp(-(t - gamma * N) / (beta * N)))
                )
                for k in range(N):
                    list_k = np.delete(np.arange(N), k)
                    # select the strata to add an increment
                    if np.sum(sigma2[k]) == 0:
                        p = np.repeat(1 / N, N)
                    else:
                        p = (
                            np.repeat(1 / N, N) * (1 - e)
                            + sigma2[k] / np.sum(sigma2[k]) * e
                        )

                    strata = np.random.choice(np.arange(N), 1, p=p)[0]
                    # generate the increment
                    u = np.random.uniform(0, 1, 1)[0]
                    cumSum = 0
                    for subset in combinations(list_k, strata):
                        cumSum += (
                            factorial(N - 1 - strata)
                            * factorial(strata)
                            / factorial(N - 1)
                        )
                        if cumSum > u:
                            S = np.array(subset, dtype=int)
                            break
                    SUk = np.append(S, k)
                    increment = self.not_twice_characteristic(
                        SUk, the_scenario
                    ) - self.not_twice_characteristic(S, the_scenario)
                    contributions[k][strata].append(increment)
                    # compute sthe standard deviation and means
                    sigma2[k, strata] = np.std(contributions[k][strata])
                    mu[k, strata] = np.mean(contributions[k][strata])
                shap = np.mean(mu, axis=0)
                var = np.zeros(N)  # variance of the estimator
                for k in range(N):
                    for strata in range(N):
                        n_k_strata = len(contributions[k][strata])
                        if n_k_strata == 0:
                            var[k] = np.Inf
                        else:
                            var[k] += sigma2[k, strata] ** 2 / n_k_strata
                        if n_k_strata > 20:
                            continuer[k][strata] = False
                    var[k] /= N ** 2
                v_max = np.max(var)
            self.name = "Stratified MC Shapley values"
            self.contributivity_scores = shap
            self.scores_std = np.sqrt(var)
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start

    # %% compute Shapley values with the support stratified sampling method

    def support(self, the_scenario, sv_accuracy=0.01, alpha=0.95):
        """Return the vector of approximated Shapley values using the stratified monte-carlo method."""

        start = timer()

        N = len(the_scenario.node_list)
        characteristic_all_node = self.not_twice_characteristic(
            np.arange(N), the_scenario
        )  # Characteristic function on all nodes

        if N == 1:
            self.name = "SSMC Shapley values"
            self.contributivity_scores = np.array([characteristic_all_node])
            self.scores_std = np.array([0])
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start
        else:
            # sampling
            gamma = 0.2
            beta = 0.0075
            t = 0
            sigma2 = np.zeros((N, N))
            mu = np.zeros((N, N))
            e = 0.0
            q = -norm.ppf((1 - alpha) / 2, loc=0, scale=1)
            v_max = 0
            continuer = []
            contributions = []
            for k in range(N):
                contributions.append(list())
                continuer.append(list())
            for k in range(N):
                for strata in range(N):
                    contributions[k].append(dict())
                    continuer[k].append(True)
            while (
                np.any(continuer) or (sv_accuracy) ** 2 < 4 * q ** 2 * v_max
            ):  # Check if the length of the confidence interval  is below the value of sv_accuracy*characteristic_all_node
                t += 1
                e = (
                    1
                    + 1 / (1 + np.exp(gamma / beta))
                    - 1 / (1 + np.exp(-(t - gamma * N) / (beta * N)))
                )
                for k in range(N):
                    list_k = np.delete(np.arange(N), k)
                    # select the strata to add an increment
                    if np.sum(sigma2[k]) == 0:
                        p = np.repeat(1 / N, N)
                    else:
                        p = (
                            np.repeat(1 / N, N) * (1 - e)
                            + sigma2[k] / np.sum(sigma2[k]) * e
                        )

                    strata = np.random.choice(np.arange(N), 1, p=p)[0]
                    # generate the increment
                    u = np.random.uniform(0, 1, 1)[0]
                    cumSum = 0
                    for subset in combinations(list_k, strata):
                        cumSum += (
                            factorial(N - 1 - strata)
                            * factorial(strata)
                            / factorial(N - 1)
                        )
                        if cumSum > u:
                            S = np.array(subset, dtype=int)
                            break
                    SUk = np.append(S, k)
                    increment = self.not_twice_characteristic(
                        SUk, the_scenario
                    ) - self.not_twice_characteristic(S, the_scenario)
                    if tuple(S) in contributions[k][strata]:
                        contributions[k][strata][tuple(S)][1] += 1
                    else:
                        contributions[k][strata][tuple(S)] = [increment, 1]
                        # computes  the intra-strata means
                        length = len(contributions[k][strata])
                        mu[k, strata] = (
                            mu[k, strata] * (length - 1) + increment
                        ) / length
                    # computes the intra-strata standard deviation
                    sigma2[k, strata] = 0
                    count = 0
                    for v in contributions[k][strata].values():
                        sigma2[k, strata] += v[1] * (v[0] - mu[k, strata]) ** 2
                        count += v[1]

                    if count > 1:
                        sigma2[k, strata] /= count - 1
                    sigma2[k, strata] = np.sqrt(sigma2[k, strata])
                shap = np.mean(mu, axis=0)
                var = np.zeros(N)  # variance of the estimator
                for k in range(N):
                    for strata in range(N):
                        n_k_strata = 0
                        for v in contributions[k][strata].values():
                            n_k_strata += v[1]
                        if n_k_strata == 0:
                            var[k] = np.Inf
                        else:
                            var[k] += sigma2[k, strata] ** 2 / n_k_strata
                        if n_k_strata > 20:
                            continuer[k][strata] = False
                    var[k] /= N ** 2
                v_max = np.max(var)
            self.name = "SSMC Shapley values"
            self.contributivity_scores = shap
            self.scores_std = np.sqrt(var)
            self.normalized_scores = self.contributivity_scores / np.sum(
                self.contributivity_scores
            )
            end = timer()
            self.computation_time = end - start
