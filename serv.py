#!/usr/bin/env python3

import argparse
import gzip
import json
import os
import sys
import tempfile
from types import SimpleNamespace


from flask import Flask, abort, request, send_file

import cisummary
import timeline

app = Flask(__name__)

try:
    with open("secret", "rb") as f:
        secret = f.read()
except FileNotFoundError:
    print("not using secret")
else:
    print(f"using secret of {len(secret)} bytes")
    app.config["SECRET_KEY"] = secret

try:
    with open("allowed_slugs.json", "rb") as f:
        allowed_slugs = set(json.load(f))
except FileNotFoundError:
    print(
        "\x1b[31;1mWARNING: Populate `allowed_slugs.json` with a list of allowed slugs or nothing will work!\x1b[m"
    )
    allowed_slugs = set()


def get_slug(vcs, org, repo):
    slug = f"{vcs}/{org}/{repo}"
    if slug not in allowed_slugs:
        abort(404)
    return slug


@app.route("/<vcs>/<org>/<repo>/master")
def master(vcs, org, repo):
    slug = get_slug(vcs, org, repo)
    pages = int(request.args.get("pages", 5))
    data, meta = cisummary.get_data(slug, "master", pages=pages, jobs=32)
    return str(cisummary.proc(slug, data, meta=meta, description="master"))


@app.route("/<vcs>/<org>/<repo>/pulls")
def pulls(vcs, org, repo):
    slug = get_slug(vcs, org, repo)
    pages = int(request.args.get("pages", 5))
    data, meta = cisummary.get_data(
        slug,
        None,
        pages=pages,
        jobs=32,
        pipeline_filter=lambda p: p.get("vcs", {})
        .get("branch", "")
        .startswith("pull/"),
    )
    return str(cisummary.proc(slug, data, meta=meta, description="pulls"))


@app.route("/<vcs>/<org>/<repo>/tags")
def tags(vcs, org, repo):
    slug = get_slug(vcs, org, repo)
    pages = int(request.args.get("pages", 12))
    data, meta = cisummary.get_data(
        slug,
        None,
        pages=pages,
        jobs=32,
        pipeline_filter=lambda p: "tag" in p.get("vcs", {}),
    )
    return str(cisummary.proc(slug, data, meta=meta, description="tags"))


@app.route("/<vcs>/<org>/<repo>/workflow_timeline/<uuid>")
def workflow_timeline(vcs, org, repo, uuid):
    with tempfile.TemporaryDirectory() as d:
        fn = os.path.join(d, "timeline.pdf")
        timeline.make(uuid, fn)
        return send_file(fn)


@app.after_request
def compress(r):
    if "Content-Encoding" in r.headers:
        return r
    try:
        data = r.get_data()
    except RuntimeError:
        return r
    r.set_data(gzip.compress(r.get_data()))
    r.headers["Content-Encoding"] = "gzip"
    return r


def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--bind", default="127.0.0.1")
    parser.add_argument("-p", "--port", type=int, default=9999)

    args = parser.parse_args(args)

    app.run(host=args.bind, port=args.port)


if __name__ == "__main__":
    exit(main(sys.argv[1:]))
