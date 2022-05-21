import python_minifier
import os


def get_imports(data):
    imports = []
    for line in data.split("\n"):
        if line.strip().startswith("import"):
            imports.append(line.strip().replace("import ", ""))

    return imports


def get_local_imports(data):
    imports = get_imports(data)
    local_imports = []
    local_import_files = []
    for import_ in imports:
        p = import_.replace(".", "/") + ".py"
        if os.path.isfile(p):
            local_imports.append(import_)
            local_import_files.append(p)

    return dict(zip(local_imports, local_import_files))


def get_from_imports(data):
    imports = {}
    for line in data.split("\n"):
        if line.strip().startswith("from "):
            im = line.replace("from ", "").split(" import ")
            imports[im[0]] = ",".join(im[1].split(", ")).split(",") if len(im[1].split(", ")) > 1 else im[1]

    return imports


def remove_imports(data):
    for line in data.split("\n"):
        if line.strip().startswith("import ") or line.strip().startswith("from "):
            data = data.replace(line, "")

    return data


def clean_repeated_imports(data):
    lines_seen = set()
    lines = []
    for line in data.split("\n"):
        if line.strip().startswith("import ") or line.strip().startswith("from "):
            if line.split(" ")[1] not in lines_seen:
                lines_seen.add(line.split(" ")[1])
                lines.append(line)
        else:
            lines.append(line)

    return "\n".join(lines)


def insert_imports(data, imports):
    data = "from types import SimpleNamespace\n" + data
    import_list = {}
    for key in imports:
        with open(imports[key], "r") as f:
            import_list[key] = f.read()

    for _import in import_list.keys():
        from_imports = get_from_imports(data)
        print(from_imports)
        content = import_list[_import]
        _imports = get_imports(content)
        _recursive_imports = get_local_imports(content)
        for _recursive_import in _recursive_imports.keys():
            print(_recursive_import)
            if _recursive_import not in _imports:
                _imports.append(_recursive_import)
                content = content.replace(_recursive_import, _recursive_imports[_recursive_import])
        content = remove_imports(content)
        for __import in _imports:
            data = "import " + __import + "\n" + data
        for from_import in from_imports.keys():
            data = "from " + from_import + " import " + from_imports[from_import] + "\n" + data
        data = data.replace("import " + _import, content)
        data = data.replace(_import + ".", "")

    data = clean_repeated_imports(data)
    return data


def minify(data):
    return python_minifier.minify(data)


if __name__ == "__main__":
    with open("main.py", "r") as _f:
        _py = _f.read()
        new = insert_imports(_py, get_local_imports(_py))
        with open("test.py", "w") as f:
            f.write(new)
