.. _logo:

Logo
====

.. image:: _static/logo/armoor-logo.png
   :width: 520px
   :alt: ARMOOR
   :class: only-light

.. image:: _static/logo/armoor-logo-dark.png
   :width: 520px
   :alt: ARMOOR
   :class: only-dark

The two interlaced O's of ARMOOR are what the library does: comparing
observations with a model.

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item::

      .. image:: _static/logo/armoor-mark.png
         :width: 100%
         :alt: The ARMOOR symbol

   .. grid-item::

      **Observations, the first O.** Five contours drawn as thin broken tracks
      that fade in and out, with stations of every size along and between them:
      real measurements, sparse and irregular, like ship routes punctuated by casts.

      **Model, the second O.** The same five contours as a continuous filled
      field. Its inner isolines are slightly offset: the model departs from what
      is observed.

      **Interlaced.** The two O's overlap over most of their width and each
      passes over the other once.

Variants
--------

.. grid:: 1 1 2 2
   :gutter: 3

   .. grid-item-card:: On navy

      .. image:: _static/logo/armoor-logo-navy.png
         :width: 100%

   .. grid-item-card:: Lowercase

      .. image:: _static/logo/armoor-logo-lowercase.png
         :width: 100%

   .. grid-item-card:: Monochrome

      .. image:: _static/logo/armoor-logo-mono.png
         :width: 100%

   .. grid-item-card:: Monochrome, white

      .. image:: _static/logo/armoor-logo-mono-white.png
         :width: 100%

   .. grid-item-card:: Avatar (GitHub, GitLab)

      .. image:: _static/logo/armoor-avatar.png
         :width: 160px

   .. grid-item-card:: Favicon

      .. image:: _static/logo/armoor-favicon.png
         :width: 64px

      Below 64 px the tracks and stations are no longer legible: the favicon and
      the monochrome versions use two plain rings.

Colours
-------

.. list-table::
   :header-rows: 1
   :widths: 25 45 30

   * - Role
     - Hex
     - Use
   * - Abyssal navy
     - ``#081B2B``
     - lettering on light grounds, dark grounds
   * - Ice blue
     - ``#CFE7F6``
     - lettering on navy
   * - Contour scale, dark grounds
     - ``#1B5A8A`` ``#3E9ED8`` ``#7CBFE8`` ``#B9DDF4`` ``#FFFFFF``
     - outer to inner contour
   * - Contour scale, light grounds
     - ``#1B5A8A`` ``#3E9ED8`` ``#7CBFE8`` ``#A6D2EF`` ``#CFE7F6``
     - stops short of white

The lettering is Manrope Bold (SIL Open Font License 1.1), shipped in
``doc/_logo/fonts/``.

Generating the logo
-------------------

The logo is drawn with matplotlib by ``doc/_logo/armoor_logo.py``, with shapely
for the boolean geometry. The documentation build calls it from ``conf.py`` and
writes the images above into ``doc/_static/logo/``; they are only redrawn when
the script or the font changes. The observation pattern comes from fixed random
seeds, so every run draws the same logo.

To export a variant by hand, from the repository root:

.. code-block:: bash

   python doc/_logo/armoor_logo.py logo -o armoor-logo.png
   python doc/_logo/armoor_logo.py logo --dark -o armoor-logo-dark.png
   python doc/_logo/armoor_logo.py logo --no-fade -o armoor-logo.svg   # fully vector
   python doc/_logo/armoor_logo.py avatar -o armoor-avatar.png --size 5.12 --dpi 100
   python doc/_logo/armoor_logo.py doc -o doc/_static/logo             # all doc images

In SVG or PDF, matplotlib cannot paint a gradient along a shape, so the fading
tracks are embedded as small clipped images; ``--no-fade`` draws solid tracks
and keeps the file fully vector.

.. dropdown:: Source of ``doc/_logo/armoor_logo.py``

   .. literalinclude:: _logo/armoor_logo.py
      :language: python
