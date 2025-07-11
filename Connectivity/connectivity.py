import pandas as pd
import random
from ete3 import Tree
import numpy as np
from collections import Counter
import argparse  # For parsing command line arguments

# Parse the phylogenetic tree file and load it as a Tree object
def parse_tree(tree_file):
    tree = Tree(tree_file, format=1)
    return tree

# Group sequences based on phylogenetic distance
def group_sequences_by_distance(tree, sequences):
    groups = {}
    for seq in sequences:
        node = tree.search_nodes(name=seq)
        if node:
            distance = node[0].dist
            if distance not in groups:
                groups[distance] = []
            groups[distance].append(seq)
    return groups

# Sample sequences from different phylogenetic groups, prioritizing sequences from different groups
def sample_from_groups_by_habitat(groups, sample_size_per_habitat, habitats, tree):
    sampled_sequences = []

    # Obtain sequences from different habitats
    habitat_sequences = {habitat: [] for habitat in set(habitats.values())}
    for group, sequences in groups.items():
        for seq in sequences:
            habitat_sequences[habitats[seq]].append(seq)

    # Traverse each habitat, sample separately for each habitat, prioritizing different groups
    for habitat, sequences in habitat_sequences.items():
        group_sequences = {group: [seq for seq in sequences if seq in groups[group]] for group in groups}
        selected = []

        # First, extract from different groups until the required number is reached
        for group, seq_list in sorted(group_sequences.items(), key=lambda x: x[0]):
            if len(selected) >= sample_size_per_habitat:
                break
            available_size = sample_size_per_habitat - len(selected)
            if len(seq_list) <= available_size:
                selected.extend(seq_list)
            else:
                selected.extend(random.sample(seq_list, available_size))

        # If insufficient, continue to supplement from the same group, alternating the selection
        if len(selected) < sample_size_per_habitat:
            remaining_size = sample_size_per_habitat - len(selected)
            group_order = sorted(group_sequences.items(), key=lambda x: x[0])

            # Alternately extract from different groups until filled
            while remaining_size > 0:
                for group, seq_list in group_order:
                    remaining_sequences = [seq for seq in seq_list if seq not in selected]
                    if remaining_sequences:
                        selected.append(random.choice(remaining_sequences))
                        remaining_size -= 1
                    if remaining_size == 0:
                        break

        sampled_sequences.extend(selected)

    # Sort sequences according to the order of the phylogenetic tree
    sampled_sequences = sort_sequences_by_tree(tree, sampled_sequences)

    return sampled_sequences

# Sort the extracted sequences according to their positions in the phylogenetic tree
def sort_sequences_by_tree(tree, sequences):
    # Get the order of all nodes in the phylogenetic tree
    tree_order = tree.get_leaf_names()
    
    # Sort the extracted sequences according to their positions in the tree
    sorted_sequences = sorted(sequences, key=lambda seq: tree_order.index(seq))
    
    return sorted_sequences

# Shuffle sequence groups with a phylogenetic distance of 0
def shuffle_identical_groups(sequences, groups, shuffle_count):
    # Only shuffle if shuffle_count is greater than 0
    if shuffle_count > 0:
        shuffled_sequences = sequences[:]
        for group in groups.values():
            group_indices = [sequences.index(seq) for seq in group if seq in sequences]
            if len(group_indices) > 1:
                shuffled_positions = random.sample(group_indices, len(group_indices))
                for i, idx in enumerate(group_indices):
                    shuffled_sequences[idx] = sequences[shuffled_positions[i]]
        return shuffled_sequences
    else:
        return sequences  # Return the original sequence order if no shuffle

# Calculate connectivity: based on the number of adjacent habitat changes
def calculate_connectivity(sequences, habitats):
    connectivity = 0
    n = len(sequences)

    for i in range(n):
        left = habitats[sequences[i]]
        right = habitats[sequences[(i + 1) % n]]

        # Only calculate the number of adjacent habitat changes
        if left != right:
            connectivity += 1

    return connectivity

# Calculate the minimum and maximum connectivity
def calculate_standard_connectivity(sequences, habitats):
    habitat_counts = Counter(habitats[seq] for seq in sequences)
    habitats_sorted = sorted(habitat_counts.keys())

    min_sequence = []
    max_sequence = []

    # Minimum connectivity: Grouping the same habitats together
    for habitat in habitats_sorted:
        min_sequence.extend([habitat] * habitat_counts[habitat])

    # Maximum connectivity: Alternating habitat arrangement
    habitat_counts_copy = habitat_counts.copy()  # Deep copy
    while sum(habitat_counts_copy.values()) > 0:
        for habitat in habitats_sorted:
            if habitat_counts_copy[habitat] > 0:
                max_sequence.append(habitat)
                habitat_counts_copy[habitat] -= 1

    # Create a virtual sequence name and habitat mapping
    min_sequence_dict = {f"Seq{i}": min_sequence[i] for i in range(len(min_sequence))}
    max_sequence_dict = {f"Seq{i}": max_sequence[i] for i in range(len(max_sequence))}

    # Calculate connectivity using virtual sequence name
    min_connectivity = calculate_connectivity(list(min_sequence_dict.keys()), min_sequence_dict)
    max_connectivity = calculate_connectivity(list(max_sequence_dict.keys()), max_sequence_dict)

    return min_connectivity, max_connectivity

# Calculate normalized connectivity and return the maximum, minimum, and average values
def calculate_normalized_connectivity(sequences, habitats, groups, shuffle_count, max_sample_size):
    all_scores = []

    # Calculate standard connectivity
    min_connectivity, max_connectivity = calculate_standard_connectivity(sequences, habitats)

    if shuffle_count == 0:
        # Do not shuffle, directly calculate the connectivity of the original data
        connectivity = calculate_connectivity(sequences, habitats)
        all_scores.append(connectivity)
    else:
        for _ in range(shuffle_count):
            shuffled_sequences = shuffle_identical_groups(sequences, groups, shuffle_count)
            connectivity = calculate_connectivity(shuffled_sequences, habitats)
            all_scores.append(connectivity)

    min_score = np.min(all_scores)
    max_score = np.max(all_scores)
    avg_score = np.mean(all_scores)

    # Normalization
    if max_connectivity != min_connectivity:
        normalized_min = ((min_score - min_connectivity) / (max_connectivity - min_connectivity)) * (1 - 1/max_sample_size) + 1/max_sample_size
        normalized_max = ((max_score - min_connectivity) / (max_connectivity - min_connectivity)) * (1 - 1/max_sample_size) + 1/max_sample_size
        normalized_avg = ((avg_score - min_connectivity) / (max_connectivity - min_connectivity)) * (1 - 1/max_sample_size) + 1/max_sample_size
    else:
        normalized_min = normalized_max = normalized_avg = 1 / max_sample_size

    return normalized_min, normalized_max, normalized_avg

# Resample sequences and habitats, and output to an Excel file
def resample_sequences_habitats(df, gene_tree, sample_tree, iterations, output_file, max_sample_size=30):
    results = []

    groups = df['Group'].unique()
    for group in groups:
        group_df = df[df['Group'] == group]
        gene_sequences = group_df['Gene'].tolist()
        sample_sequences = group_df['Sample'].tolist()
        habitats = dict(zip(group_df['Gene'], group_df['Habitat']))
        sample_habitats = dict(zip(group_df['Sample'], group_df['Habitat']))

        # Get the sample count for each habitat
        habitat_counts = group_df.groupby('Habitat').size()

        # If max_sample_size is 0, use the smallest number of habitats in each group
        if max_sample_size == 0:
            min_habitat_count = habitat_counts.min()
        else:
            min_habitat_count = min(habitat_counts.min(), max_sample_size)

        # Ensure randomization by resetting the random seed at the beginning of each loop
        for i in range(iterations):
            random.seed()  # Do not pass parameters to regenerate the random seed

            # Perform habitat-based sampling for genes, using the smallest number of habitat samples for balancing
            gene_groups = group_sequences_by_distance(gene_tree, gene_sequences)
            balanced_genes = sample_from_groups_by_habitat(gene_groups, min_habitat_count, habitats, gene_tree)

            # Perform habitat-based sampling for samples, using the smallest number of habitat samples for balancing
            sample_groups = group_sequences_by_distance(sample_tree, sample_sequences)
            balanced_samples = sample_from_groups_by_habitat(sample_groups, min_habitat_count, sample_habitats, sample_tree)

            results.append({
                'Iteration': i + 1,
                'Group': group,
                'Gene Avg': calculate_normalized_connectivity(balanced_genes, habitats, gene_groups, 0, min_habitat_count)[2],
                'Sampled Genes': balanced_genes,
                'Sampled Samples': balanced_samples
            })

    # Keep only the necessary columns in the result
    df_result = pd.DataFrame(results)
    df_result = df_result[['Iteration', 'Group', 'Gene Avg', 'Sampled Genes', 'Sampled Samples']]

    # Save the results to an Excel file
    df_result.to_excel(output_file, index=False)

# Main function to run the entire analysis process
def main(habitat_file, gene_tree_file, sample_tree_file, iterations=999, output_file='paixu_cattle99_30.xlsx', max_sample_size=30):
    df = pd.read_csv(habitat_file)
    gene_tree = parse_tree(gene_tree_file)
    sample_tree = parse_tree(sample_tree_file)

    # Match common data between habitat file, gene tree and sample tree
    gene_sequences = set(df['Gene'])
    sample_sequences = set(df['Sample'])
    
    # Get the common sequences across all three files
    common_sequences = gene_sequences.intersection(sample_sequences)
    common_sequences = common_sequences.intersection(set(gene_tree.get_leaf_names()))

    # Filter the data for the common sequences
    df_filtered = df[df['Gene'].isin(common_sequences)]
    
    # Run the resampling and connectivity analysis
    resample_sequences_habitats(df_filtered, gene_tree, sample_tree, iterations, output_file, max_sample_size)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Resample sequences and calculate connectivity.')
    parser.add_argument('--habitat_file', required=True, help='Path to the habitat file (CSV)')
    parser.add_argument('--gene_tree_file', required=True, help='Path to the gene tree file (Newick format)')
    parser.add_argument('--sample_tree_file', required=True, help='Path to the sample tree file (Newick format)')
    parser.add_argument('--iterations', type=int, default=999, help='Number of iterations for sampling')
    parser.add_argument('--output_file', required=True, help='Output file name for results')
    parser.add_argument('--max_sample_size', type=int, default=30, help='Maximum sample size per habitat')

    args = parser.parse_args()

    main(args.habitat_file, args.gene_tree_file, args.sample_tree_file, iterations=args.iterations, output_file=args.output_file, max_sample_size=args.max_sample_size)
