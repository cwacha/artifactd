# Welcome to artifactd

Artifactd is a lightweight python implementation of an artifact storage system
similar to jFrog's [Artifactory](https://www.jfrog.com/open-source/) or
Sonatype's [Nexus](http://www.sonatype.org/nexus/). It provides a two
repositories for 'release' and 'snapshot' artifacts. In the 'release'
repository artifacts are write-once and cannot be overwritten. In the
'snapshot' repository old artifacts are remove automatically. It usually
keeps the most recent 5 snapshots (configurable).

In addition it supports the display of README.md file in a folder (like
this one). Its content is Markdown which is also used by
[GitHub](https://github.com). It uses the python
[markdown2](https://github.com/trentm/python-markdown2) implementation as
well as the github stylesheets to make it look nice. Markdown is a light
text markup format and a processor to convert that to HTML.
The originator describes it as follows:

> Markdown is a text-to-HTML conversion tool for web writers.
> Markdown allows you to write using an easy-to-read,
> easy-to-write plain text format, then convert it to
> structurally valid XHTML (or HTML).
>
> -- <http://daringfireball.net/projects/markdown/>

Travis-ci.org test status: [![Build Status](https://travis-ci.org/cwacha/artifactd.svg?branch=master)](https://travis-ci.org/cwacha/artifactd)

# Quick Usage
## Deploy Artifacts

To upload artifacts just run the following `curl` command

    curl -T filename.pkg -X PUT http://hostname:4070/artifacts/snapshot/project/v1.0/filename.pkg

or

    curl -T filename.pkg -X PUT http://hostname:4070/artifacts/release/project/v1.0/filename.pkg

## Download Artifacts

To download artifacts just use `curl` in the similar way

    curl -O http://hostname:4070/artifacts/release/project/v1.0/filename.pkg

