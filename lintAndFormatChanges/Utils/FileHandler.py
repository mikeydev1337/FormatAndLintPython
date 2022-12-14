import getpass
import subprocess
import sys
from glob import glob
from pathlib import Path
from typing import List, Set

ALLOWLISTPATH = Path(__file__).parent / "../config/allowlist.txt"
DENYLISTPATH = Path(__file__).parent / "../config/denylist.txt"


def createTmpDir(baseDir: Path) -> Path:
    """
    This function creates a numbered directory
    based on the current user's username. The
    directory is created before being returned
    to the user.

    Args:
        baseDir: The base directory to work inside of.

    Returns:
        The directory to to store files into.

    Raises:
        ValueError: If a non-numbered directory exists where the numbered directory
                    will be created.
    """
    userTmpDir = baseDir / getpass.getuser()
    userTmpDir.mkdir(parents=True, exist_ok=True)
    subdirs = []
    for subdir in userTmpDir.iterdir():
        try:
            subdirs.append(int(subdir.name))
        except ValueError as invalidDir:
            print(
                f"Error: unexpected sub-directory '{subdir}'\n"
                f"{userTmpDir.resolve()} should only contain numbered directories.",
                file=sys.stderr,
            )
            raise invalidDir

    revision = max(subdirs) + 1 if subdirs else 0
    revisionDir = userTmpDir / str(revision)
    revisionDir.mkdir()

    return revisionDir


def getMergeBase(start: str, end: str = "HEAD") -> str:
    """
    This function gets the merge base of two commits.

    Args:
        start: The first reference point (valid git identifier).
        end:   The second reference point (valid git identifier).

    Returns:
        The merge base of the two reference points.

    Raises:
        subprocess.CalledProcessError: If there is an error when using subprocess
                                       to get the merge-base.
    """
    try:
        return subprocess.check_output(["git", "merge-base", start, end]).strip().decode()
    except subprocess.CalledProcessError as e:
        print("Error occurred while getting merge base of commits.", file=sys.stderr)
        raise e


def getChangedFiles(fromCommit: str, toCommit: str = "HEAD") -> List[Path]:
    """
    This function gets the list of files
    that have changed between two commits.

    Args:
        fromCommit: The starting commit.
        toCommit:   The ending commit.

    Returns:
        The list of all the files that have changed.
    """
    try:
        pathStrings = (
            subprocess.check_output(["git", "diff", "--name-only", fromCommit, toCommit]).strip().decode().split("\n")
        )
    except subprocess.CalledProcessError as e:
        print("Error occurred while getting changed files.", file=sys.stderr)
        raise e

    changed = [Path(pathString) for pathString in pathStrings]
    changed = [path for path in changed if path.exists()]

    return changed


def getAllTrackedFiles() -> List[Path]:
    """
    This function gets the list of all files
    that are currently being tracked by Git.

    Returns:
        The list of all the files that are tracked by Git.

    Raises:
        subprocess.CalledProcessError: If there is an error when using subprocess
                                       to get the list of tracked files.
    """
    try:
        pathStrings = (
            subprocess.check_output(["git", "ls-tree", "-r", "--full-tree", "--name-only", "HEAD"])
            .strip()
            .decode()
            .split("\n")
        )
    except subprocess.CalledProcessError as e:
        print("Error occurred while getting tracked files.", file=sys.stderr)
        raise e

    tracked = [Path(pathString) for pathString in pathStrings]

    return tracked


def getGlobsFromFile(globlistFile: Path) -> Set[Path]:
    """
    This function resolves a list of glob patterns from a file.

    Args:
        globlistFile: The file that contains the glob patterns
                      to resolve.

    Returns:
        The set of all unique paths that result from the glob.
    """
    globStrings = globlistFile.read_text().split("\n")
    pathSet: Set[Path] = set()
    for globString in globStrings:
        pathStrings = glob(globString, recursive=True)
        pathSet.update(Path(pathString) for pathString in pathStrings)
    assert all(path.exists() for path in pathSet)

    return pathSet


def getFormattablePaths() -> Set[Path]:
    """
    This function gets the set of all files that can be seen by presubmit.
    It will resolve all allowlisted globs and all denylisted globs,
    and return allowlisted Paths that don't also appear in the glob of
    denylisted Paths.

    Returns:
        The set of valid Paths to be used.
    """
    allowlistPaths = getGlobsFromFile(ALLOWLISTPATH)
    denylistPaths = getGlobsFromFile(DENYLISTPATH)

    return allowlistPaths - denylistPaths


def getFilesToFormat(changedSince: str) -> Set[Path]:
    """
    This function gets the set of files that will be formatted by presubmit.

    Args:
        changedSince: The starting commit to compare against
                      when getting the set of files changed.

    Returns:
        The set of files to be formatted.
    """
    mergeBase = getMergeBase(changedSince)
    changedFiles = getChangedFiles(mergeBase)
    formattablePaths = getFormattablePaths()

    return set(changedFiles) & formattablePaths


def getTrackedFormattablePaths() -> Set[Path]:
    """
    This function gets the set of files that can be formatted by presubmit
    and are tracked by Git.

    Returns:
        The set of files that are tracked and can be formatted.
    """
    trackedFiles = getAllTrackedFiles()
    formattablePaths = getFormattablePaths()

    return set(trackedFiles) & formattablePaths
