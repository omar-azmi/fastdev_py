### fastdev_py

FastAPI development server that JIT preprocess TS, TSX, SCSS, etc... files without littering your filesystem at all. <br>
also, has in-memory caching of preprocessed files. <br>
under the hood, it uses Deno along with a webassembly version of esbuild to transform your requested files

