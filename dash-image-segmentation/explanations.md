This app uses machine learning to compute the segmentation of an image from a
few user-provided annotations. Besides Plotly and Dash, it uses off-the-shelf
algorithms and estimators from [scikit-image](https://scikit-image.org/) and
[scikit-learn](https://scikit-learn.org).

### User annotations

The training set is built with plotly's
[shape drawing tools](https://plotly.com/python/shapes/#drawing-shapes-with-a-mouse-on-cartesian-plots):
the freehand `drawopenpath` mode draws "squiggles" on the parts of the image you
want to label, and `drawrect` draws rectangle outlines. Use a different class
color for every kind of object, and adjust the brush width to annotate features
of different sizes. Each new mark triggers a callback through the figure's
[relayoutData event](https://dash.plotly.com/interactive-graphing).

### Computation of features

Deep learning models learn features directly from the data, but need large
training sets and a lot of compute. Instead, each pixel is described by local
features:

- the average intensity in a small region around the pixel
- the average magnitude of gradients in the same region
- measures of local texture in this region

They're computed by blurring the image with Gaussian kernels of several sizes
(the blurring scale), then measuring the color intensity, gradient intensity, or
eigenvalues of the Hessian matrix, using
[`skimage.feature.multiscale_basic_features`](https://scikit-image.org/docs/stable/api/skimage.feature.html#skimage.feature.multiscale_basic_features).

### Model training and prediction

The features of the annotated pixels train a scikit-learn
[random forest classifier](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.RandomForestClassifier.html),
an [ensemble method](https://scikit-learn.org/stable/modules/ensemble.html) that
combines the predictions of many decision trees. The trained model then
classifies all the unlabeled pixels, giving a segmentation of the image. Add
more marks where pixels are misclassified to improve it, or download the
classifier to segment new images of the same kind (for example, a time series).
