## DO 

1. clean configuration handling in cli.py
    - make generic config file for any utility
2. add multiple filetypes to scanner (besides tiff, tif, add tar, jpeg, etc)
3. add better progress_bar and handling using object oriented
    - nested progress bars without multiple Progress() instantiations
4. modular ingest_tiles function with smaller for uri in 
5. write Experiment class for running and storing experiments with different configurations for ingest_tiles
6. add timer function for measuring time delta between operation begin/end
7. make InJester object to create an ingestion instance for experimentation and modularity
8. make an output file named after the csv if it doesnt exist 

9. make a whirlwind shell utility that puts us into a shell environment for easier functionality
    - phase1: minimum sufficient version: 
            - whirlwind enters a shell environment
            - help, exit commands
            - existing commands are parsed as argv
    - phase2: session state
            - variables, variable expansion liks $out, shell config
    - phase3: quality of life - full shell functionalty
            - history
            - autocomplete
            - cd, pwd, etc 
