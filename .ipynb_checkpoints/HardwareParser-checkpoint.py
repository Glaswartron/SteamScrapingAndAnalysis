import regex

def process_graphics_regex(graphics : str):
    nvidiaPattern = "(?:GeForce)*\s{0,1}(?:GTX|RTX)\s[0-9]{1,4}\s{0,1}(?:Ti|SUPER)*"
    amdPattern = "(?:Radeon)*\s{0,1}(?:RX)\s{0,1}[0-9]{0,4}\s{0,1}(?:XT)*"
    nvidiaMatches = regex.findall(nvidiaPattern, graphics)
    amdMatches = regex.findall(amdPattern, graphics)
    nvidia = nvidiaMatches[0].strip() if len(nvidiaMatches) > 0 else ""
    amd = amdMatches[0].strip() if len(amdMatches) > 0 else ""
    if len(nvidia) > 0 and not nvidia.startswith("GeForce"):
        nvidia = "GeForce " + nvidia
    return nvidia, amd

def process_graphics(graphics : str):
    graphics = graphics.lower()
    nvidia, amd = "", ""
    delimiters = [" or ", "/", ",", "|"]
    nvidia_designators = ["nvidia", "geforce", "gtx", "rtx"]
    amd_designators = ["amd", "ryzen"]

    if "or equivalent" in graphics:
        graphics = graphics.replace("or equivalent", "")

    if not any(d in graphics for d in delimiters):
        if any(n in graphics for n in nvidia_designators):
            return graphics, ""
        elif any(a in graphics for a in amd_designators):
            return "", graphics
        else:
            return "", ""

    ds = list(filter(lambda d: d in graphics, delimiters))
    
    if len(ds) == 1 and graphics.count(ds[0]) == 1:
        parts = graphics.split(ds[0])
        if any(n in parts[0] for n in nvidia_designators):
            nvidia = parts[0]
            if any(a in parts[1] for a in amd_designators):
                amd = parts[1]
        elif any(a in parts[0] for a in amd_designators):
            amd = parts[0]
            if any(n in parts[1] for n in nvidia_designators):
                nvidia = parts[1]
        return nvidia, amd
    
    if len(ds) > 1 or graphics.count(ds[0]) > 1:
        possible_parts = []
        for d in ds:
            for p in graphics.split(d):
                possible_parts.append(p)
        nvidias = list(filter(lambda p: any(n in p for n in nvidia_designators), possible_parts))
        nvidias.sort(key = lambda n: len(n))
        nvidia = nvidias[0] if len(nvidias) > 0 else ""
        amds = list(filter(lambda p: any(a in p for a in amd_designators), possible_parts))
        amds.sort(key = lambda a: len(a))
        amd = amds[0] if len(amds) > 0 else ""
        return nvidia, amd
    
    return nvidia, amd