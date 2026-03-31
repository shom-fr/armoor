What's new
##########

Develop
=======

New features
------------

Breaking changes
----------------

- The dependency on ``xoa.cf`` has been replaced by ``xoa.meta``.
  This enables installation via conda-forge. Users relying on internal
  ``xoa.cf`` APIs should migrate to ``xoa.meta``.

Deprecations
------------

Bug fixes
---------

- Fixed a decoding error (``KeyError: 'ptemp'``) in satellite SST and
  other dataset loaders caused by ``xoa.meta`` selecting the wrong
  MetaSpecs during inference. Specs are now applied explicitly with
  ``cfspecs.decode(ds)`` instead of relying on the ``set_meta_specs``
  context manager.

- Fixed ``XoaCoordsError: Coordinate type not found`` when reordering
  dimensions after a curvilinear-to-rectilinear grid transform. Added
  ``axis`` attributes to all coordinate entries in the armoor CF
  configuration files so that ``xoa.meta`` can correctly resolve
  dimension types (X, Y, Z, T).

Documentation
-------------
