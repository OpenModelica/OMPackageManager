import GitHub
import Glob
import JSON
import LibGit2
import OMJulia
import DataStructures

function log(x...)
    println(stdout, x...)
    flush(stdout)
end

log("Start")

@enum SupportLevel fullSupport support experimental obsolete unknown noSupport

supportLevel = Dict{String,SupportLevel}("fullSupport" => fullSupport, "support" => support, "experimental" => experimental, "obsolete" => obsolete, "unknown" => unknown)

function findMatchingLevel(s::AbstractString, levels)
  local vn
  try
    vn = VersionNumber(s)
  catch
    return nothing
  end
  for level in levels
    matched = false
    if level[1] == "*"
      matched = true
    elseif startswith(level[1], ">=") && vn >= VersionNumber(level[1][3:end])
      matched = true
    elseif level[1] == s
      matched = true
    end
    if matched
      return level[2]
    end
  end
  return nothing
end

function getSupportLevel(tagName::AbstractString, levels)::SupportLevel
  res = findMatchingLevel(tagName, levels)
  if res == nothing
    return noSupport
  end
  return supportLevel[res]
end

function lessTag(x, y)
  if x["support"] == y["support"]
    return VersionNumber(x["tag"]) > VersionNumber(y["tag"])
  end
  return x["support"] < y["support"]
end

function run_test()
  gh_auth = ENV["GITHUB_AUTH"]
  myauth = GitHub.authenticate(gh_auth)

  log("Start run")
  omc = OMJulia.OMCSession()

  data = JSON.parsefile("test.json"; dicttype=DataStructures.SortedDict)
  serverdata = DataStructures.SortedDict()
  if isfile("server.json")
    serverdata = JSON.parsefile("server.json"; dicttype=DataStructures.SortedDict)
  end

  #repos, page_data = GitHub.repos("modelica-3rdParty", auth=myauth)
  #for r in repos
  #  log(r)
  #end

  if !isdir("cache")
    mkdir("cache")
  end

  namesInFile = Set()
  for key in keys(data)
    for name in data[key]["names"]
      if name in namesInFile
        throw(ErrorException(key * " exists multiple times"))
      end
      push!(namesInFile, name)
    end
  end

  for key in keys(data)
    entry = data[key]
    if haskey(entry, "github")
      r = GitHub.repo(entry["github"]; auth=myauth)

      if !haskey(serverdata, key)
        serverdata[key] = DataStructures.SortedDict()
        log("Did not have stored data for " * key)
      end
      #if haskey(serverdata[key], "updated_at") && r.updated_at == serverdata[key]["updated_at"]
      #  continue
      #end
      if !haskey(serverdata[key], "tags")
        serverdata[key]["tags"] = DataStructures.SortedDict()
      end
      ignoreTags = Set()
      if haskey(entry, "ignore-tags")
        ignoreTags = Set(entry["ignore-tags"])
      end
      #serverdata[key]["updated_at"] = r.updated_at

      branches, page_data = GitHub.branches(r; auth=myauth)
      tags, page_data = GitHub.tags(r; auth=myauth)
      tagsDict = serverdata[key]["tags"]

      repopath = joinpath("cache", key)

      for tag in tags
        tagName = match(r"/git/refs/tags/(?<name>.*)", tag.url.path)[:name]
        sha = tag.object["sha"]
        if tagName in ignoreTags
          continue
        end
        if !haskey(tagsDict, tagName)
          tagsDict[tagName] = DataStructures.SortedDict()
        end
        thisTag = tagsDict[tagName]
        if !haskey(thisTag, "sha") || (thisTag["sha"] != sha)
          ghurl = "https://github.com/" * entry["github"] * ".git"
          if isdir(repopath)
            gitrepo = LibGit2.GitRepo(repopath)
            LibGit2.fetch(gitrepo)
            if !all(h.url == ghurl for h in LibGit2.fetchheads(gitrepo))
              log("Removing repository " * ghurl)
              rm(repopath, recursive=true)
            end
          end
          if !isdir(repopath)
            LibGit2.clone(ghurl, repopath)
          end
          gitrepo = LibGit2.GitRepo(repopath)
          LibGit2.checkout!(gitrepo, sha)

          provided = DataStructures.SortedDict()
          for libname in entry["names"]
            hits = readdir(Glob.GlobMatch(joinpath(repopath,"package.mo")))
            if size(hits,1) == 1
              if libname != entry["names"][1]
                continue
              end
            else
              hits = cat(
                readdir(Glob.GlobMatch(joinpath(repopath,libname,"package.mo"))),
                readdir(Glob.GlobMatch(joinpath(repopath,libname*" *","package.mo"))),
                readdir(Glob.GlobMatch(joinpath(repopath,libname*".mo"))),
                readdir(Glob.GlobMatch(joinpath(repopath,libname*" *.mo"))),
                readdir(Glob.GlobMatch(joinpath(repopath,libname*"*",libname * ".mo"))),
                readdir(Glob.GlobMatch(joinpath(repopath,libname*"*",libname * " *.mo")))
                ; dims=1
              )
            end
            if size(hits,1) != 1
              log(string(size(hits,1)) * " hits for " * libname * " in " * tagName)
              continue
            end
            OMJulia.sendExpression(omc, "clear()")
            if haskey(entry, "standard")
              grammar = findMatchingLevel(tagName, entry["standard"])
              if grammar == nothing
                grammar = "latest"
              end
            else
              grammar = "latest"
            end
            OMJulia.sendExpression(omc, "setCommandLineOptions(\"--std=" * grammar * "\")")

            if !OMJulia.sendExpression(omc, "loadFile(\"" * hits[1] * "\")")
              log("Failed to load file " * hits[1] * " in " * tagName) # OMJulia.sendExpression(omc, "OpenModelica.Scripting.getErrorString()"))
              continue
            end
            classNamesAfterLoad::Array{Symbol,1} = OMJulia.sendExpression(omc, "getClassNames()")
            if !(Symbol(libname) in classNamesAfterLoad)
              print("Did not load the library? ")
              log(classNamesAfterLoad)
              continue
            end
            version = OMJulia.sendExpression(omc, "getVersion("*libname*")")
            version = string(version == "" ? VersionNumber(tagName) : VersionNumber(version))
            uses = [[e[1],string(VersionNumber(e[2]))] for e in DataStructures.SortedDict(OMJulia.sendExpression(omc, "getUses("*libname*")"))]
            # Get conversions
            provided[libname] = DataStructures.SortedDict("version" => version, "uses" => uses)
          end
          if isempty(provided)
            log("Broken for " * key * " " * tagName)
            thisTag["broken"]=true
            continue
          end
          thisTag["libs"] = provided
          thisTag["sha"] = sha
        end
        level = getSupportLevel(tagName, entry["support"])
        thisTag["support"] = level
      end
      # sort!(tagsSorted; lt=lessTag)
      serverdata[key]["tags"] = tagsDict
    end
  end

  open("server.json", "w") do io
    write(io, JSON.json(serverdata,2))
  end

  log(GitHub.rate_limit(auth=myauth))
end

@time run_test()
@time run_test()
