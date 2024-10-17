# Get the root directory of this repository (the parent dir of this script)
PAPER_DIR="$(dirname "$(readlink -fm "$0")")/oarcdt"

rm -f "$PAPER_DIR"/paper.pdf

docker run --rm \
    --volume "$PAPER_DIR":/data \
    --user "$(id -u)":"$(id -g)" \
    --env JOURNAL=joss \
    openjournals/inara
