# Change Log

Versioned according to [Semantic Versioning](http://semver.org/).

## Unreleased

Fixed:

 * set pcGtsId to METS file ID everwhere

## [0.1.0] - 2020-08-14

Changed:

 * put derived images under output fileGrp, using file ID suffixes

## [0.0.5] - 2020-07-08

Fixed:

 * update requirements (needs newer `ocrd, skimage, pillow`)
 * all: fix typo in `level-of-operation=region`
 * `ocrd-skimage-denoise-raw`: skip images with too little noise
 * `ocrd-skimage-*`: preserve color depth in image format

## [0.0.4] - 2020-06-10

Changed:

  * `ocrd-preprocess-image`: check constant image size

Added:

  * First set of example parameter files for ocrd-preprocess-image


## [0.0.3] - 2020-06-10

Changed:

  * Renamed `ocrd-process-image` to `ocrd-preprocess-image`
  
Added:

  * `ocrd-skimage-normalize` (wraps SciKit-Image `exposure` funcs)
  * `ocrd-skimage-denoise-raw` (wraps SciKit-Image `denoise_wavelet`)
  * `ocrd-skimage-denoise` (wraps SciKit-Image `remove_small_holes/objects`)

## [0.0.2] - 2020-06-09

Added:

  * `ocrd-skimage-binarize` (wraps SciKit-Image thresholding)

## [0.0.1] - 2020-06-08

Added:

  * `ocrd-process-image` (generic shell-wrapped image preprocessor)
