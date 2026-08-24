from whitenoise.storage import CompressedManifestStaticFilesStorage


class NonStrictCompressedManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    """
    Custom Whitenoise storage that suppresses MissingFileError during collectstatic
    and runtime for missing source maps or non-critical referenced files.
    """
    manifest_strict = False
