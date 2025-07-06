System requirements
   Operating systems: Windows 10 and Ubuntu 20.04.6 LTS (Focal Fossa)
   Required:
   Python v3.12.3;
   pandas v2.2;
   ete3 v3.3;
   numpy v1.26.4;
   random v3.12.3;
   collections v3.12.3.

Update
   pip install pandas==2.2;
   pip install ete3==3.3;
   pip install numpy==1.26.4.

Run
python connectivity.py --habitat_file Habitat_pig.csv --gene_tree_file Gene_pig.tree --sample_tree_file Sample_pig.tree --iterations 10 --output_file Result_pig.xlsx --max_sample_size 30
