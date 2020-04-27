# -*- coding: utf-8 -*-
"""
This enables to parameterize a desired scenario to mock a multi-partner ML project.
"""

from keras.datasets import mnist
from sklearn.model_selection import train_test_split
import datetime
import numpy as np
import matplotlib.pyplot as plt
import uuid
import pandas as pd
from loguru import logger
import operator
import random

from partner import Partner


class Scenario:
    def __init__(self, params, experiment_path):

        # Identify and get a dataset for running experiments
        self.dataset_name = "MNIST"
        (x_train, y_train), (x_test, y_test) = mnist.load_data()
        self.nb_samples_used = len(x_train)

        # The train set has to be split into a train set and a validation set for early stopping
        self.x_train, self.x_val, self.y_train, self.y_val = train_test_split(
            x_train, y_train, test_size=0.2, random_state=42
        )
        self.x_test = x_test
        self.y_test = y_test

        # Performance of the model trained in a distributed way on all partners
        self.federated_test_score = int
        self.federated_computation_time_sec = int

        # List of all partners defined in the scenario
        self.partners_list = []

        # List of contributivity measures selected and computed in the scenario
        self.contributivity_list = []

        # --------------------------------------
        #  Definition of collaborative scenarios
        # --------------------------------------

        # partners mock different partners in a collaborative data science project
        # For defining the number of partners
        self.partners_count = params["partners_count"]

        # For configuring the respective sizes of the partners' datasets
        # Should the partners receive an equivalent amount of samples each or receive different amounts?
        # Define the percentages of samples per partner
        # Sum has to equal 1 and number of items has to equal partners_count
        self.amounts_per_partner = params["amounts_per_partner"]

        # For configuring if data samples are split between partners randomly or in a stratified way...
        # ... so that they cover distinct areas of the samples space
        if "samples_split_option" in params:
            self.samples_split_option = params["samples_split_option"]
        else:
            self.samples_split_option = "random"

        # For configuring if the data of the partners are corrupted or not (useful for testing contributivity measures)
        if "corrupted_datasets" in params:
            self.corrupted_datasets = params["corrupted_datasets"]
        else:
            self.corrupted_datasets = ["not_corrupted"] * self.partners_count

        # ---------------------------------------------------
        #  Configuration of the distributed learning approach
        # ---------------------------------------------------

        # When training on a single partner,
        # the test set can be either the local partner test set or the global test set
        if "single_partner_test_mode" in params:
            self.single_partner_test_mode = params[
                "single_partner_test_mode"
            ]  # Toggle between 'local' and 'global'
        else:
            self.single_partner_test_mode = "global"

        # Define how federated learning aggregation steps are weighted. Toggle between 'uniform' and 'data_volume'
        # Default is 'uniform'
        if "aggregation_weighting" in params:
            self.aggregation_weighting = params["aggregation_weighting"]
        else:
            self.aggregation_weighting = "uniform"

        # Number of epochs and mini-batches in ML training
        if "epoch_count" in params:
            self.epoch_count = params["epoch_count"]
            assert self.epoch_count > 0
        else:
            self.epoch_count = 40

        if "minibatch_count" in params:
            self.minibatch_count = params["minibatch_count"]
            assert self.minibatch_count > 0
        else:
            self.minibatch_count = 20

        # Early stopping stops ML training when performance increase is not significant anymore
        # It is used to optimize the number of epochs and the execution time
        if "is_early_stopping" in params:
            self.is_early_stopping = params["is_early_stopping"]
        else:
            self.is_early_stopping = True

        # -----------------------------------------------------------------
        #  Configuration of contributivity measurement methods to be tested
        # -----------------------------------------------------------------

        # Contributivity methods
        ALL_METHODS_LIST = [
            "Shapley values",
            "Independant scores",
            "TMCS",
            "ITMCS",
            "IS_lin_S",
            "IS_reg_S",
            "AIS_Kriging_S",
            "SMCS",
            "WR_SMC",
        ]

        # List of Contributivity methods runned by default if no method was given in the config file
        DEFAULT_METHODS_LIST = ["Shapley values", "Independant scores", "TMCS"]

        self.methods = []
        if "methods" in params and params["methods"]:

            for method in params["methods"]:
                if method in ALL_METHODS_LIST:
                    self.methods.append(method)
                else:
                    raise Exception("Method [" + method + "] is not in methods list.")

        else:
            self.methods = DEFAULT_METHODS_LIST

        # -------------
        # Miscellaneous
        # -------------

        # The quick demo parameters overwrites previously defined paramaters to make the scenario faster to compute
        if "is_quick_demo" in params and params["is_quick_demo"]:
            # Use less data and less epochs to speed up the computations
            logger.info("Quick demo: limit number of data and number of epochs.")
            self.x_train = self.x_train[:1000]
            self.y_train = self.y_train[:1000]
            self.x_val = self.x_val[:500]
            self.y_val = self.y_val[:500]
            self.x_test = self.x_test[:500]
            self.y_test = self.y_test[:500]
            self.epoch_count = 3
            self.minibatch_count = 2

        # -------
        # Outputs
        # -------

        now = datetime.datetime.now()
        now_str = now.strftime("%Y-%m-%d_%Hh%M")
        self.scenario_name = (
                str(self.samples_split_option)
                + "_"
                + str(self.partners_count)
                + "_"
                + str(self.amounts_per_partner)
                + "_"
                + str(self.corrupted_datasets)
                + "_"
                + str(self.single_partner_test_mode)
                + "_"
                + now_str
                + "_"
                + uuid.uuid4().hex[
                  :3
                  ]  # This is to be sure 2 distinct scenarios do no have the same name
        )

        self.short_scenario_name = (
                str(self.partners_count)
                + " "
                + str(self.amounts_per_partner)
        )

        self.save_folder = experiment_path / self.scenario_name

        self.save_folder.mkdir(parents=True, exist_ok=True)

        # ------------------------------------------------
        # Print the description of the scenario configured
        # ------------------------------------------------

        # Describe scenario
        print("\n### Description of data scenario configured:")
        print("- Number of partners defined:", self.partners_count)
        print("- Data distribution scenario chosen:", self.samples_split_option)
        print("- Test data distribution scenario chosen:", self.single_partner_test_mode)
        print("- Weighting option:", self.aggregation_weighting)
        print(
            "- Number of epochs and mini-batches: "
            + str(self.epoch_count)
            + " epochs and "
            + str(self.minibatch_count)
            + " mini-batches"
        )

        # Describe data
        print("\n### Data loaded: ", self.dataset_name)
        print("- " + str(len(self.x_train)) + " train data with " + str(len(self.y_train)) + " labels")
        print("- " + str(len(self.x_val)) + " val data with " + str(len(self.y_val)) + " labels")
        print("- " + str(len(self.x_test)) + " test data " + str(len(self.y_test)) + " labels")

    def append_contributivity(self, contributivity):

        self.contributivity_list.append(contributivity)

    def instantiate_scenario_partners(self):

        self.partners_list = [Partner(i) for i in range(self.partners_count)]

    def split_data_advanced(self):
        """Advanced split: Populates the partners with their train and test data (not pre-processed)"""

        x_train = self.x_train
        y_train = self.y_train
        x_test = self.x_test
        y_test = self.y_test
        partners_list = self.partners_list
        amounts_per_partner = self.amounts_per_partner
        advanced_split_option = self.samples_split_option

        # Compose the lists of partners with data samples from shared clusters and those with specific clusters
        for p in partners_list:
            p.cluster_count = int(advanced_split_option[p.id][0])
            p.cluster_split_option = advanced_split_option[p.id][1]
        partners_with_shared_clusters = [p for p in partners_list if p.cluster_split_option == 'shared']
        partners_with_specific_clusters = [p for p in partners_list if p.cluster_split_option == 'specific']
        partners_with_shared_clusters.sort(key=operator.attrgetter("cluster_count"), reverse=True)
        partners_with_specific_clusters.sort(key=operator.attrgetter("cluster_count"), reverse=True)

        # Compose the list of different labels in the dataset
        labels = list(set(y_train))
        random.seed(42)
        random.shuffle(labels)

        # Check coherence of the split option:
        nb_diff_labels = len(labels)
        specific_clusters_count = sum([p.cluster_count for p in partners_with_specific_clusters])
        if partners_with_shared_clusters:
            shared_clusters_count = max([p.cluster_count for p in partners_with_shared_clusters])
        else:
            shared_clusters_count = 0
        assert specific_clusters_count + shared_clusters_count <= nb_diff_labels

        # Stratify the dataset into clusters per labels
        x_train_for_cluster, y_train_for_cluster, count_per_cluster = {}, {}, {}
        for label in labels:
            idx_in_full_trainset = np.where(y_train == label)
            x_train_for_cluster[label] = x_train[idx_in_full_trainset]
            y_train_for_cluster[label] = y_train[idx_in_full_trainset]
            count_per_cluster[label] = len(y_train_for_cluster[label])

        # For each partner compose the list of clusters from which they will draw data samples
        index = 0
        for p in partners_with_specific_clusters:
            p.clusters_list = labels[index:index + p.cluster_count]
            index += p.cluster_count

        shared_clusters = labels[index:index + shared_clusters_count]
        for p in partners_with_shared_clusters:
            p.clusters_list = random.sample(shared_clusters, k=p.cluster_count)

        # We need to enforce the relative data amounts configured.
        # It might not be possible to distribute all data samples, depending on...
        # ... the coherence of the relative data amounts and the split option.
        # We will compute a resize factor to determine the total nb of samples to be distributed per partner

        # For partners getting data samples from specific clusters...
        # ... compare the nb of available samples vs. the nb of samples initially configured
        resize_factor_specific = 1
        for p in partners_with_specific_clusters:
            nb_available_samples = sum([count_per_cluster[cl] for cl in p.clusters_list])
            nb_samples_configured = int(amounts_per_partner[p.id] * len(y_train))
            ratio = nb_available_samples / nb_samples_configured
            resize_factor_specific = min(resize_factor_specific, ratio)

        # For each partner getting data samples from shared clusters:
        # ... compute the nb of samples initially configured and resize it,
        # ... then sum per cluster how many samples are needed.
        # Then, find if a cluster is requested more samples than it got, and if yes by which factor
        resize_factor_shared = 1
        nb_samples_needed_per_cluster = dict.fromkeys(shared_clusters, 0)
        for p in partners_with_shared_clusters:
            initial_amount_resized = int(amounts_per_partner[p.id] * len(y_train) * resize_factor_specific)
            initial_amount_resized_per_cluster = int(initial_amount_resized / p.cluster_count)
            for cl in p.clusters_list:
                nb_samples_needed_per_cluster[cl] += initial_amount_resized_per_cluster
        for cl in nb_samples_needed_per_cluster:
            resize_factor_shared = min(resize_factor_shared, count_per_cluster[cl] / nb_samples_needed_per_cluster[cl])

        # Compute the final resize factor
        final_resize_factor = resize_factor_specific * resize_factor_shared

        # Size correctly each partner's subset. For each partner:
        for p in partners_list:
            p.final_nb_samples = int(amounts_per_partner[p.id] * len(y_train) * final_resize_factor)
            p.final_nb_samples_p_cluster = int(p.final_nb_samples / p.cluster_count)
        self.nb_samples_used = sum([p.final_nb_samples for p in partners_list])
        final_relative_nb_samples = [round(p.final_nb_samples / self.nb_samples_used, 2) for p in partners_list]

        # Partners receive their subsets
        shared_clusters_index = dict.fromkeys(shared_clusters, 0)
        for p in partners_list:
            list_arrays_x, list_arrays_y = [], []
            if p in partners_with_shared_clusters:
                for cl in p.clusters_list:
                    idx = shared_clusters_index[cl]
                    list_arrays_x.append(x_train_for_cluster[cl][idx:idx + p.final_nb_samples_p_cluster])
                    list_arrays_y.append(y_train_for_cluster[cl][idx:idx + p.final_nb_samples_p_cluster])
                    shared_clusters_index[cl] += p.final_nb_samples_p_cluster
            elif p in partners_with_specific_clusters:
                for cl in p.clusters_list:
                    list_arrays_x.append(x_train_for_cluster[cl][:p.final_nb_samples_p_cluster])
                    list_arrays_y.append(y_train_for_cluster[cl][:p.final_nb_samples_p_cluster])
            p.x_train = np.concatenate(list_arrays_x)
            p.y_train = np.concatenate(list_arrays_y)
            p.x_test = x_test
            p.y_test = y_test

        # Check coherence of number of mini-batches versus partner with small dataset
        assert self.minibatch_count <= min([len(p.x_train) for p in self.partners_list])

        # Print for controlling
        print("\n### Splitting data among partners:")
        print("Advanced split performed.")
        print("Nb of samples split amongst partners: ", str(self.nb_samples_used))
        print("- Partners' relative nb of samples: " + str(final_relative_nb_samples))
        print("  (versus initially configured: " + str(amounts_per_partner))
        for partner in self.partners_list:
            print("- Partner #" + str(partner.id) + ": ", end="")
            print(str(len(partner.x_train)) + " train samples, ", end="")
            print("y_train unique values: " + str(partner.clusters_list))

        return 0

    def split_data(self):
        """Populates the partners with their train and test data (not pre-processed)"""

        # Fetch parameters of scenario
        x_train = self.x_train
        y_train = self.y_train
        x_test = self.x_test
        y_test = self.y_test

        # Configure the desired splitting scenario - Datasets sizes
        # Should the partners receive an equivalent amount of samples each...
        # ... or receive different amounts?

        # Check the percentages of samples per partner and control its coherence
        assert len(self.amounts_per_partner) == self.partners_count
        assert np.sum(self.amounts_per_partner) == 1

        # Then we parameterize this via the splitting_indices to be passed to np.split
        # This is to transform the percentages from the scenario configuration into indices where to split the data
        splitting_indices = np.empty((self.partners_count - 1,))
        splitting_indices[0] = self.amounts_per_partner[0]
        for i in range(self.partners_count - 2):
            splitting_indices[i + 1] = (
                    splitting_indices[i] + self.amounts_per_partner[i + 1]
            )
        splitting_indices_train = (splitting_indices * len(y_train)).astype(int)
        splitting_indices_test = (splitting_indices * len(y_test)).astype(int)
        # print('- Splitting indices defined (for train data):', splitting_indices_train) # VERBOSE

        # Configure the desired data distribution scenario

        # Create a list of indexes of the samples
        train_idx = np.arange(len(y_train))
        test_idx = np.arange(len(y_test))

        # In the 'stratified' scenario we sort MNIST by labels
        if self.samples_split_option == "stratified":
            # Sort MNIST by labels
            y_sorted_idx = y_train.argsort()
            y_train = y_train[y_sorted_idx]
            x_train = x_train[y_sorted_idx]

        # In the 'random' scenario we shuffle randomly the indexes
        elif self.samples_split_option == "random":
            np.random.seed(42)
            np.random.shuffle(train_idx)

        # If neither 'stratified' nor 'random', we raise an exception
        else:
            raise NameError(
                "This samples_split_option scenario ["
                + self.samples_split_option
                + "] is not recognized."
            )

        # Do the splitting among partners according to desired scenarios

        # Split data between partners
        train_idx_idx_list = np.split(train_idx, splitting_indices_train)
        test_idx_idx_list = np.split(test_idx, splitting_indices_test)

        # Populate partners
        partner_idx = 0
        for train_idx, test_idx in zip(train_idx_idx_list, test_idx_idx_list):
            current_partner = self.partners_list[partner_idx]

            # Train data
            x_partner_train = x_train[train_idx, :]
            y_partner_train = y_train[
                train_idx,
            ]

            # Test data (for use in scenarios with single_partner_test_mode == 'local')
            x_partner_test = x_test[test_idx]
            y_partner_test = y_test[test_idx]

            current_partner.x_train = x_partner_train
            current_partner.x_test = x_partner_test
            current_partner.y_train = y_partner_train
            current_partner.y_test = y_partner_test

            current_partner.final_nb_samples = len(current_partner.x_train)
            current_partner.clusters_list = list(set(current_partner.y_train))

            partner_idx += 1

        # Check coherence of number of mini-batches versus smaller partner
        assert self.minibatch_count <= (min(self.amounts_per_partner) * len(x_train))

        self.nb_samples_used = sum([len(p.x_train) for p in self.partners_list])

        # Print for controlling
        print("\n### Splitting data among partners:")
        print("Simple split performed.")
        print("Nb of samples split amongst partners: ", str(self.nb_samples_used))
        for partner in self.partners_list:
            print("- Partner #" + str(partner.id) + ": ", end="")
            print(str(partner.final_nb_samples) + " train samples, ", end="")
            print("y_train unique values: " + str(partner.clusters_list))

        return 0

    def plot_data_distribution(self):

        for i, partner in enumerate(self.partners_list):

            plt.subplot(self.partners_count, 1, i + 1)  # TODO share y axis
            data_count = np.bincount(partner.y_train)

            # Fill with 0
            while len(data_count) < 10:
                data_count = np.append(data_count, 0)

            plt.bar(np.arange(0, 10), data_count)
            plt.ylabel("partner " + str(partner.id))

        plt.suptitle("Data distribution")
        plt.xlabel("Digits")
        # plt.show()  # DEBUG
        plt.savefig(self.save_folder / "data_distribution.png")

    def to_file(self):

        out = ""
        out += "Dataset name: " + self.dataset_name + "\n"
        out += "Number of data samples - train: " + str(len(self.x_train)) + "\n"
        out += "Number of data samples - test: " + str(len(self.x_test)) + "\n"
        out += "partners count: " + str(self.partners_count) + "\n"
        out += (
                "Percentages of data samples per partner: " + str(self.amounts_per_partner) + "\n"
        )
        out += (
                "Data samples split option: "
                + str(self.samples_split_option)
                + "\n"
        )
        out += (
                "When training on a single partner, global or local testset: "
                + self.single_partner_test_mode
                + "\n"
        )
        out += "Number of epochs: " + str(self.epoch_count) + "\n"
        out += "Number of mini-batches: " + str(self.minibatch_count) + "\n"
        out += "Early stopping on? " + str(self.is_early_stopping) + "\n"
        out += (
                "Test score of federated training: " + str(self.federated_test_score) + "\n"
        )
        out += "\n"

        out += str(len(self.contributivity_list)) + " contributivity methods: " + "\n"

        for contrib in self.contributivity_list:
            out += str(contrib) + "\n\n"

        target_file_path = self.save_folder / "results_summary.txt"

        with open(target_file_path, "w", encoding="utf-8") as f:
            f.write(out)

    def to_dataframe(self):

        df = pd.DataFrame()

        for contrib in self.contributivity_list:

            dict_results = {}

            for i in range(self.partners_count):
                # Scenario data
                dict_results["dataset_name"] = self.dataset_name
                dict_results["train_data_samples_count"] = len(self.x_train)
                dict_results["test_data_samples_count"] = len(self.x_test)
                dict_results["nb_samples_used"] = self.nb_samples_used
                dict_results["partners_count"] = self.partners_count
                dict_results["amounts_per_partner"] = self.amounts_per_partner
                dict_results["samples_split_option"] = self.samples_split_option
                dict_results["single_partner_test_mode"] = self.single_partner_test_mode
                dict_results["epoch_count"] = self.epoch_count
                dict_results["minibatch_count"] = self.minibatch_count
                dict_results["is_early_stopping"] = self.is_early_stopping
                dict_results["federated_test_score"] = self.federated_test_score
                dict_results["federated_computation_time_sec"] = self.federated_computation_time_sec
                dict_results["scenario_name"] = self.scenario_name
                dict_results["short_scenario_name"] = self.short_scenario_name
                dict_results["aggregation_weighting"] = self.aggregation_weighting

                # Contributivity data
                dict_results["contributivity_method"] = contrib.name
                dict_results["contributivity_scores"] = contrib.contributivity_scores
                dict_results["contributivity_stds"] = contrib.scores_std
                dict_results["computation_time_sec"] = contrib.computation_time_sec
                dict_results["first_characteristic_calls_count"] = contrib.first_charac_fct_calls_count

                # partner data
                dict_results["partner_id"] = i
                dict_results["amount_per_partner"] = self.amounts_per_partner[i]
                dict_results["contributivity_score"] = contrib.contributivity_scores[i]
                dict_results["contributivity_std"] = contrib.scores_std[i]

                df = df.append(dict_results, ignore_index=True)

        df.info()

        return df
