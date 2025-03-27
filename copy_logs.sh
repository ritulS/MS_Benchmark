#!/bin/bash

# Define the URL to download from
BASE_URL="http://node9:9090/mewbie_ritul_logs/_data/"
# Use wget to download all files recursively from the given URL
wget -r -np -nH --cut-dirs=2 -P ./logs/last_run "$BASE_URL"

# # Define the URL to download from
BASE_URL="http://node6:9090/mewbie_ritul_logs/_data/"
# Use wget to download all files recursively from the given URL
wget -r -np -nH --cut-dirs=2 -P ./logs/last_run "$BASE_URL"


BASE_URL="http://localhost:9090/mewbie_ritul_logs/_data/"
# Use wget to download all files recursively from the given URL
wget -r -np -nH --cut-dirs=2 -P ./logs/last_run "$BASE_URL"


# # Define the URL to download from
BASE_URL="http://node8:9090/mewbie_ritul_logs/_data/"
# Use wget to download all files recursively from the given URL
wget -r -np -nH --cut-dirs=2 -P ./logs/last_run "$BASE_URL"

# python3 -m http.server 9090
