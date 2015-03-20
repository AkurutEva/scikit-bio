# ----------------------------------------------------------------------------
# Copyright (c) 2013--, scikit-bio development team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING.txt, distributed with this software.
# ----------------------------------------------------------------------------

from __future__ import absolute_import, division, print_function
from future.builtins import range
from future.utils import viewitems, with_metaclass
from six import string_types

import re
import collections
from abc import ABCMeta, abstractmethod
from itertools import product

import numpy as np
from scipy.spatial.distance import hamming

from skbio._base import SkbioObject
from skbio.sequence import SequenceError
from skbio.util import classproperty


class Sequence(collections.Sequence, SkbioObject):
    """Base class for biological sequences.

    Parameters
    ----------
    sequence : python collections.Sequence (e.g., str, list or tuple)
        The biological sequence.
    id : str, optional
        The sequence id (e.g., an accession number).
    description : str, optional
        A description or comment about the sequence (e.g., "green
        fluorescent protein").
    quality : 1-D array_like, int, optional
        Phred quality scores stored as nonnegative integers, one per sequence
        character. If provided, must be the same length as the biological
        sequence. Can be a 1-D ``numpy.ndarray`` of integers, or a structure
        that can be converted to this representation using ``numpy.asarray``. A
        copy will *not* be made if `quality` is already a 1-D ``numpy.ndarray``
        with an ``int`` ``dtype``. The array will be made read-only (i.e., its
        ``WRITEABLE`` flag will be set to ``False``).

    Attributes
    ----------
    sequence
    id
    description
    quality

    Raises
    ------
    skbio.sequence.SequenceError
        If `quality` is not the correct shape.

    See Also
    --------
    NucleotideSequence
    DNA
    RNA

    Notes
    -----
    `Sequence` objects are immutable. Where applicable, methods
    return a new object of the same class.
    Subclasses are typically defined by methods relevant to only a specific
    type of biological sequence, and by containing characters only contained in
    the IUPAC standard character set [1]_ for that molecule type.

    Examples
    --------
    >>> from skbio.sequence import Sequence
    >>> s = Sequence('GGUCGUGAAGGA')
    >>> t = Sequence('GGUCCUGAAGGU')

    References
    ----------
    .. [1] Nomenclature for incompletely specified bases in nucleic acid
       sequences: recommendations 1984.
       Nucleic Acids Res. May 10, 1985; 13(9): 3021-3030.
       A Cornish-Bowden

    """
    default_write_format = 'fasta'

    def __init__(self, sequence, id="", description="", quality=None):
        if not isinstance(sequence, string_types):
            sequence = ''.join(sequence)
        self._sequence = sequence

        self._set_id(id)
        self._description = description
        self._set_quality(quality)

    def _set_id(self, id_):
        if isinstance(id_, string_types):
            self._id = id_
        else:
            raise ValueError('ID %r is not valid.' % (id_,))

    def __contains__(self, other):
        """The in operator.

        Parameters
        ----------
        other : str
            The putative subsequence.

        Returns
        -------
        bool
            Indicates whether `other` is contained in `self`.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUCGUGAAGGA')
        >>> 'GGU' in s
        True
        >>> 'CCC' in s
        False

        .. shownumpydoc

        """
        return other in self._sequence

    def __eq__(self, other):
        """The equality operator.

        Biological sequences are equal if their sequence is the same and they
        are the same type. Identifier, description, and quality scores
        **are ignored**.

        Parameters
        ----------
        other : `Sequence`
            The sequence to test for equality against.

        Returns
        -------
        bool
            Indicates whether `self` and `other` are equal.

        See Also
        --------
        __ne__
        equals

        Notes
        -----
        See ``Sequence.equals`` for more fine-grained control of
        equality testing.

        This method is equivalent to
        ``self.equals(other, ignore=['id', 'description', 'quality'])``.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUCGUGAAGGA')
        >>> t = Sequence('GGUCGUGAAGGA')
        >>> s == t
        True
        >>> u = Sequence('GGUCGUGACCGA')
        >>> u == t
        False

        Note that even though the quality scores do not match between ``u`` and
        ``v``, they are considered equal:

        >>> v = Sequence('GGUCGUGACCGA',
        ...                        quality=[1, 5, 3, 3, 2, 42, 100, 9, 10, 55,
        ...                                 42, 42])
        >>> u == v
        True

        .. shownumpydoc

        """
        return self.equals(other, ignore=['id', 'description', 'quality'])

    def __getitem__(self, i):
        """The indexing operator.

        Parameters
        ----------
        i : int, slice, or sequence of ints
            The position(s) to return from the `Sequence`. If `i` is
            a sequence of ints, these are assumed to be indices in the sequence
            to keep.

        Returns
        -------
        Sequence
            New biological sequence containing the character(s) at position(s)
            `i` in the current `Sequence`. If quality scores are
            present, the quality score at position(s) `i` will be included in
            the returned sequence. ID and description are also included.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUCGUGAAGGA')

        Obtain a single character from the biological sequence:

        >>> s[1]
        <Sequence: G (length: 1)>

        Obtain a slice:

        >>> s[7:]
        <Sequence: AAGGA (length: 5)>

        Obtain characters at the following indices:

        >>> s[[3, 4, 7, 0, 3]]
        <Sequence: CGAGC (length: 5)>

        .. shownumpydoc

        """
        # TODO update this method when #60 is resolved. we have to deal with
        # discrepancies in indexing rules between str and ndarray... hence the
        # ugly code
        try:
            try:
                seq = self.sequence[i]
                qual = self.quality[i] if self.has_quality() else None
            except TypeError:
                seq = [self.sequence[idx] for idx in i]

                if self.has_quality():
                    qual = [self.quality[idx] for idx in i]
                else:
                    qual = None
        except IndexError:
            raise IndexError(
                "Position %r is out of range for %r." % (i, self))

        return self.copy(sequence=seq, quality=qual)

    def __hash__(self):
        """The hash operator.

        Returns
        -------
        int
            The hash of the `Sequence`.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUCGUGAAGGA')
        >>> hash(s)
        -1080059835405276950

        .. shownumpydoc

        """
        return hash(self._sequence)

    def __iter__(self):
        """The iter operator.

        Returns
        -------
        iterator
            Position iterator for the `Sequence`.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUC')
        >>> for c in s: print(c)
        G
        G
        U
        C

        .. shownumpydoc

        """
        return iter(self._sequence)

    def __len__(self):
        """The len operator.

        Returns
        -------
        int
            The length of the `Sequence`.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUC')
        >>> len(s)
        4

        .. shownumpydoc

        """
        return len(self._sequence)

    def __ne__(self, other):
        """The inequality operator.

        Biological sequences are not equal if their sequence is different or
        they are not the same type. Identifier, description, and quality scores
        **are ignored**.

        Parameters
        ----------
        other : `Sequence`
            The sequence to test for inequality against.

        Returns
        -------
        bool
            Indicates whether `self` and `other` are not equal.

        See Also
        --------
        __eq__
        equals

        Notes
        -----
        See ``Sequence.equals`` for more fine-grained control of
        equality testing.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUCGUGAAGGA')
        >>> t = Sequence('GGUCGUGAAGGA')
        >>> s != t
        False
        >>> u = Sequence('GGUCGUGACCGA')
        >>> u != t
        True

        .. shownumpydoc

        """
        return not (self == other)

    def __repr__(self):
        """The repr method.

        Returns
        -------
        str
            Returns a string representation of the object.

        Notes
        -----
        String representation contains the class name, the first ten characters
        of the sequence followed by ellipses (or the full sequence
        and no ellipses, if the sequence is less than 11 characters long),
        followed by the sequence length.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUCGUGAAGGA')
        >>> repr(s)
        '<Sequence: GGUCGUGAAG... (length: 12)>'
        >>> t = Sequence('ACGT')
        >>> repr(t)
        '<Sequence: ACGT (length: 4)>'
        >>> t
        <Sequence: ACGT (length: 4)>

        .. shownumpydoc

        """
        first_ten = self.sequence[:10]
        cn = self.__class__.__name__
        length = len(self)
        if length > 10:
            ellipses = "..."
        else:
            ellipses = ""
        return '<%s: %s%s (length: %d)>' % (cn, first_ten, ellipses, length)

    def __reversed__(self):
        """The reversed operator.

        Returns
        -------
        iterator
            Reverse position iterator for the `Sequence`.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUC')
        >>> for c in reversed(s): print(c)
        C
        U
        G
        G

        .. shownumpydoc

        """
        return reversed(self._sequence)

    def __str__(self):
        """The str operator

        Returns
        -------
        str
            String representation of the `Sequence`. This will be the
            full sequence, but will not contain information about the type,
            identifier, description, or quality scores.

        See Also
        --------
        to_fasta
        id
        description
        __repr__

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUC')
        >>> str(s)
        'GGUC'
        >>> print(s)
        GGUC

        .. shownumpydoc

        """
        return self.sequence

    @property
    def sequence(self):
        """String containing underlying biological sequence characters.

        A string representing the characters of the biological sequence.

        Notes
        -----
        This property is not writeable.

        """
        return self._sequence

    @property
    def id(self):
        """ID of the biological sequence.

        A string representing the identifier (ID) of the biological sequence.

        Notes
        -----
        This property is not writeable.

        """
        return self._id

    @property
    def description(self):
        """Description of the biological sequence.

        A string representing the description of the biological sequence.

        Notes
        -----
        This property is not writeable.

        """
        return self._description

    @property
    def quality(self):
        """Quality scores of the characters in the biological sequence.

        A 1-D ``numpy.ndarray`` of nonnegative integers representing Phred
        quality scores for each character in the biological sequence, or
        ``None`` if quality scores are not present.

        Notes
        -----
        This property is not writeable. A copy of the array is *not* returned.
        The array is read-only (i.e., its ``WRITEABLE`` flag is set to
        ``False``).

        """
        return self._quality

    def has_quality(self):
        """Return bool indicating presence of quality scores in the sequence.

        Returns
        -------
        bool
            ``True`` if the biological sequence has quality scores, ``False``
            otherwise.

        See Also
        --------
        quality

        """
        return self.quality is not None

    def copy(self, **kwargs):
        """Return a copy of the current biological sequence.

        Returns a copy of the current biological sequence, optionally with
        updated attributes specified as keyword arguments.

        Parameters
        ----------
        kwargs : dict, optional
            Keyword arguments passed to the ``Sequence`` (or
            subclass) constructor. The returned copy will have its attributes
            updated based on the values in `kwargs`. If an attribute is
            missing, the copy will keep the same attribute as the current
            biological sequence. Valid attribute names are `'sequence'`,
            `'id'`, `'description'`, and `'quality'`. Default behavior is to
            return a copy of the current biological sequence without changing
            any attributes.

        Returns
        -------
        Sequence
            Copy of the current biological sequence, optionally with updated
            attributes based on `kwargs`. Will be the same type as the current
            biological sequence (`self`).

        Notes
        -----
        This is a shallow copy, but since biological sequences are immutable,
        it is conceptually the same as a deep copy.

        This method is the preferred way of creating new instances from an
        existing biological sequence, instead of calling
        ``self.__class__(...)``, as the latter can be error-prone (e.g.,
        forgetting to propagate attributes to the new instance).

        Examples
        --------
        Create a biological sequence:

        >>> from skbio import Sequence
        >>> seq = Sequence('AACCGGTT', id='id1',
        ...                          description='biological sequence',
        ...                          quality=[4, 2, 22, 23, 1, 1, 1, 9])

        Create a copy of ``seq``, keeping the same underlying sequence of
        characters and quality scores, while updating ID and description:

        >>> new_seq = seq.copy(id='new-id', description='new description')

        Note that the copied biological sequence's underlying sequence and
        quality scores are the same as ``seq``:

        >>> new_seq.sequence
        'AACCGGTT'
        >>> new_seq.quality
        array([ 4,  2, 22, 23,  1,  1,  1,  9])

        The ID and description have been updated:

        >>> new_seq.id
        'new-id'
        >>> new_seq.description
        'new description'

        The original biological sequence's ID and description have not been
        changed:

        >>> seq.id
        'id1'
        >>> seq.description
        'biological sequence'

        """
        defaults = {
            'sequence': self.sequence,
            'id': self.id,
            'description': self.description,
            'quality': self.quality
        }
        defaults.update(kwargs)
        return self.__class__(**defaults)

    def equals(self, other, ignore=None):
        """Compare two biological sequences for equality.

        By default, biological sequences are equal if their sequence,
        identifier, description, and quality scores are the same and they are
        the same type.

        Parameters
        ----------
        other : Sequence
            The sequence to test for equality against.
        ignore : iterable of str, optional
            List of features to ignore in the equality test. By default, all
            features must be the same for two biological sequences to be
            considered equal. Features that can be ignored are ``'type'``,
            ``'id'``, ``'description'``, ``'quality'``, and ``'sequence'``.

        Returns
        -------
        bool
            Indicates whether `self` and `other` are equal.

        See Also
        --------
        __eq__
        __ne__

        Examples
        --------
        Define two biological sequences that have the same underlying sequence
        of characters:

        >>> from skbio import Sequence
        >>> s = Sequence('GGUCGUGAAGGA')
        >>> t = Sequence('GGUCGUGAAGGA')

        The two sequences are considered equal because they are the same type,
        their underlying sequence of characters are the same, and their
        optional attributes (id, description, and quality scores) were not
        provided:

        >>> s.equals(t)
        True
        >>> t.equals(s)
        True

        Define another biological sequence with a different sequence of
        characters than the previous two biological sequences:

        >>> u = Sequence('GGUCGUGACCGA')
        >>> u.equals(t)
        False

        Define a biological sequence with the same sequence of characters as
        ``u``, but with different identifier and quality scores:
        >>> v = Sequence('GGUCGUGACCGA', id='abc',
        ...                        quality=[1, 5, 3, 3, 2, 42, 100, 9, 10, 55,
        ...                                 42, 42])

        By default, the two sequences are *not* considered equal because their
        identifiers and quality scores do not match:

        >>> u.equals(v)
        False

        By specifying that the quality scores and identifier should be ignored,
        they now compare equal:

        >>> u.equals(v, ignore=['quality', 'id'])
        True

        """
        if ignore is None:
            ignore = {}

        # Checks are ordered from least to most expensive.
        if 'type' not in ignore and self.__class__ != other.__class__:
            return False

        if 'id' not in ignore and self.id != other.id:
            return False

        if 'description' not in ignore and \
                self.description != other.description:
            return False

        # Use array_equal instead of (a == b).all() because of this issue:
        #     http://stackoverflow.com/a/10582030
        if 'quality' not in ignore and not np.array_equal(self.quality,
                                                          other.quality):
            return False

        if 'sequence' not in ignore and self.sequence != other.sequence:
            return False

        return True

    def count(self, subsequence):
        """Returns the number of occurences of subsequence.

        Parameters
        ----------
        subsequence : str
            The subsequence to count occurences of.

        Returns
        -------
        int
            The number of occurrences of substring in the `Sequence`.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUC')
        >>> s.count('G')
        2

        """
        return self._sequence.count(subsequence)

    def distance(self, other, distance_fn=None):
        """Returns the distance to other

        Parameters
        ----------
        other : `Sequence`
            The `Sequence` to compute the distance to.
        distance_fn : function, optional
            Function used to compute the distance between `self` and `other`.
            If ``None`` (the default), `scipy.spatial.distance.hamming` will be
            used.

        Returns
        -------
        float
            The distance between `self` and `other`.

        Raises
        ------
        skbio.sequence.SequenceError
            If ``len(self) != len(other)``

        See Also
        --------
        fraction_diff
        fraction_same
        skbio.DistanceMatrix
        scipy.spatial.distance.hamming

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUC')
        >>> t = Sequence('AGUC')
        >>> s.distance(t)
        0.25
        >>> def dumb_dist(s1, s2): return 0.42
        >>> s.distance(t, dumb_dist)
        0.42

        """
        if len(self) != len(other):
            raise SequenceError(
                "Sequences do not have equal length. "
                "Distance can only be computed between "
                "Sequences of equal length.")
        if distance_fn is None:
            distance_fn = hamming
        return distance_fn(self, other)

    def fraction_diff(self, other):
        """Return fraction of positions that differ relative to `other`

        Parameters
        ----------
        other : `Sequence`
            The `Sequence` to compare against.

        Returns
        -------
        float
            The fraction of positions that differ between `self` and `other`.

        Raises
        ------
        skbio.sequence.SequenceError
            If ``len(self) != len(other)``.

        See Also
        --------
        distance
        fraction_same
        scipy.spatial.distance.hamming

        Notes
        -----
        Computed as the Hamming distance between `self` and `other`. This is
        available in addition to `distance` in case the `distance` method is
        updated to use something other than ``scipy.spatial.distance.hamming``
        as the default distance metric. So, if you specifically want the
        fraction of positions that differ, you should use this function instead
        of `distance` to ensure backward compatibility.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUC')
        >>> t = Sequence('AGUC')
        >>> s.fraction_diff(t)
        0.25

        """
        return self.distance(other, distance_fn=hamming)

    def fraction_same(self, other):
        """Return fraction of positions that are the same relative to `other`

        Parameters
        ----------
        other : `Sequence`
            The `Sequence` to compare against.

        Returns
        -------
        float
            The fraction of positions that are the same between `self` and
            `other`.

        Raises
        ------
        skbio.sequence.SequenceError
            If ``len(self) != len(other)``.

        See Also
        --------
        distance
        fraction_diff
        scipy.spatial.distance.hamming

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUC')
        >>> t = Sequence('AGUC')
        >>> s.fraction_same(t)
        0.75

        """
        return 1. - self.fraction_diff(other)

    def index(self, subsequence):
        """Return the position where subsequence first occurs

        Returns
        -------
        int
            The position where `subsequence` first occurs in the
            `Sequence`.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('ACACGACGTT-')
        >>> s.index('ACG')
        2

        """
        try:
            return self._sequence.index(subsequence)
        except ValueError:
            raise ValueError(
                "%s is not present in %r." % (subsequence, self))

    def k_words(self, k, overlapping=True):
        """Get the list of words of length k

        Parameters
        ----------
        k : int
            The word length.
        overlapping : bool, optional
            Defines whether the k-words should be overlapping or not
            overlapping.

        Returns
        -------
        iterator of Sequences
            Iterator of words of length `k` contained in the
            Sequence.

        Raises
        ------
        ValueError
            If k < 1.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('ACACGACGTT')
        >>> [str(kw) for kw in s.k_words(4, overlapping=False)]
        ['ACAC', 'GACG']
        >>> [str(kw) for kw in s.k_words(3, overlapping=True)]
        ['ACA', 'CAC', 'ACG', 'CGA', 'GAC', 'ACG', 'CGT', 'GTT']

        """
        if k < 1:
            raise ValueError("k must be greater than 0.")

        sequence_length = len(self)

        if overlapping:
            step = 1
        else:
            step = k

        for i in range(0, sequence_length - k + 1, step):
            yield self[i:i+k]

    def k_word_counts(self, k, overlapping=True):
        """Get the counts of words of length k

        Parameters
        ----------
        k : int
            The word length.
        overlapping : bool, optional
            Defines whether the k-words should be overlapping or not
            overlapping.

        Returns
        -------
        collections.Counter
            The counts of words of length `k` contained in the
            Sequence.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('ACACAT')
        >>> s.k_word_counts(3, overlapping=True)
        Counter({'ACA': 2, 'CAC': 1, 'CAT': 1})

        """
        k_words = self.k_words(k, overlapping)
        return collections.Counter((str(seq) for seq in k_words))

    def k_word_frequencies(self, k, overlapping=True):
        """Get the frequencies of words of length `k`

        Parameters
        ----------
        k : int
            The word length.
        overlapping : bool, optional
            Defines whether the k-words should be overlapping or not
            overlapping. This is only relevant when `k` > 1.

        Returns
        -------
        collections.defaultdict
            The frequencies of words of length `k` contained in the
            ``Sequence``.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('ACACAT')
        >>> s.k_word_frequencies(3, overlapping=True)
        defaultdict(<type 'float'>, {'CAC': 0.25, 'ACA': 0.5, 'CAT': 0.25})

        """
        if overlapping:
            num_words = len(self) - k + 1
        else:
            num_words = len(self) // k

        result = collections.defaultdict(float)
        k_word_counts = self.k_word_counts(k, overlapping=overlapping)
        for word, count in viewitems(k_word_counts):
            result[str(word)] = count / num_words
        return result

    def _set_quality(self, quality):
        if quality is not None:
            quality = np.asarray(quality)

            if quality.ndim == 0:
                # We have something scalar-like, so create a single-element
                # vector to store it.
                quality = np.reshape(quality, 1)

            if quality.shape == (0,):
                # cannot safe cast an empty vector from float to int
                cast_type = 'unsafe'
            else:
                cast_type = 'safe'

            quality = quality.astype(int, casting=cast_type, copy=False)
            quality.flags.writeable = False

            if quality.ndim != 1:
                raise SequenceError(
                    "Phred quality scores must be 1-D.")
            if len(quality) != len(self):
                raise SequenceError(
                    "Number of Phred quality scores (%d) must match the "
                    "number of characters in the biological sequence (%d)." %
                    (len(quality), len(self._sequence)))
            if (quality < 0).any():
                raise SequenceError(
                    "Phred quality scores must be greater than or equal to "
                    "zero.")

        self._quality = quality

    def regex_iter(self, regex, retrieve_group_0=False):
        """Find patterns specified by regular expression

        Parameters
        ----------
        regex : SRE_Pattern
            A compiled regular expression (e.g., from re.compile) with
            finditer method
        retrieve_group_0 : bool, optional
            Defaults to ``False``. If ``True``, group(0) will be included in
            each list of tuples, which represents the shortest possible
            substring of the full sequence that contains all the other groups

        Returns
        -------
        generator
            yields lists of 3-tuples. Each 3-tuple represents a group from the
            matched regular expression, and contains the start of the hit, the
            end of the hit, and the substring that was hit
        """
        start = 0 if retrieve_group_0 else 1

        for match in regex.finditer(self._sequence):
            for g in range(start, len(match.groups())+1):
                yield (match.start(g), match.end(g), match.group(g))


class IUPACSequence(with_metaclass(ABCMeta, Sequence)):
    _number_of_extended_ascii_codes = 256
    _ascii_lowercase_boundary = 90
    __validation_mask = None

    @classproperty
    def _validation_mask(cls):
        # TODO These masks could be defined (as literals) on each concrete
        # object. For now, memoize!
        if cls.__validation_mask is None:
            cls.__validation_mask = np.invert(np.bincount(
                np.fromstring(''.join(cls.alphabet), dtype=np.uint8),
                minlength=cls._number_of_extended_ascii_codes).astype(bool))
        return cls.__validation_mask

    @classproperty
    def alphabet(cls):
        """Return the set of characters allowed in an `IUPACSequence`.

        Returns
        -------
        set
            Characters that are allowed in a valid `IUPACSequence`.

        """
        return cls.degenerate_chars | cls.nondegenerate_chars | cls.gap_chars

    @classproperty
    def gap_chars(cls):
        """Return the set of characters defined as gaps.

        Returns
        -------
        set
            Characters defined as gaps.

        """
        return set('-.')

    @classproperty
    def degenerate_chars(cls):
        """Return the degenerate IUPAC characters.

        Returns
        -------
        set
            Degenerate IUPAC characters.

        """
        return set(cls.degenerate_map)

    @abstractmethod
    @classproperty
    def nondegenerate_chars(cls):
        """Return the non-degenerate IUPAC characters.

        Returns
        -------
        set
            Non-degenerate IUPAC characters.

        """
        pass

    @abstractmethod
    @classproperty
    def degenerate_map(cls):
        """Return the mapping of degenerate to non-degenerate characters.

        Returns
        -------
        dict of sets
            Mapping of IUPAC degenerate character to the set of
            non-degenerate IUPAC characters it represents.

        """
        pass

    # Do not use super here because the implementation is dramatically
    # different from optimization.
    def __init__(self, sequence, id="", description="", quality=None,
                 validate=True):
        if not isinstance(sequence, string_types):
            sequence = ''.join(sequence)
        self._sequence = sequence
        self._set_id(id)
        self._description = description
        self._set_sequence(sequence, validate)
        self._set_quality(quality)

    def __str__(self):
        return str(self._chars.view('|S%d' % self._chars.size)[0])

    def __len__(self):
        return self._bytes.size

    def __iter__(self):
        """The iter operator.

        Returns
        -------
        iterator
            Position iterator for the `IUPACSequence`.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUC')
        >>> for c in s: print(c)
        G
        G
        U
        C

        .. shownumpydoc

        """
        return iter(self._chars)

    def _set_sequence(self, sequence, validate):
        """Munge the sequence data into a numpy array."""
        is_ndarray = isinstance(sequence, np.ndarray)
        if is_ndarray:
            if np.issubdtype(sequence.dtype, np.uint8):
                pass
            elif np.issubdtype(sequence.dtype, '|S1'):
                sequence = sequence.view(np.uint8)
            else:
                raise TypeError("Can only create sequence from numpy.ndarray"
                                " of dtype np.uint8 or '|S1'.")
        else:
            sequence = np.fromstring(sequence, dtype=np.uint8)

        if sequence.size == 0:
            raise ValueError("Cannot create empty sequence.")

        if validate:
            lowercase = sequence > self._ascii_lowercase_boundary
            if np.any(lowercase):
                if is_ndarray:
                    sequence = sequence.copy()
                # ASCII is built such that the difference between uppercase and
                # lowercase is the 6th bit.
                sequence[lowercase] ^= 32

            # This is the fastest way that we have found to identify the
            # presence or absence of certain characters (numbers).
            # It works by multiplying a mask where the numbers which are
            # permitted have a zero at their index, and all others have a one.
            # The result is a vector which will propogate counts of invalid
            # numbers and remove counts of valid numbers, so that we need only
            # see if the array is empty to determine validity.
            invalid_characters = np.bincount(
                sequence, minlength=self._number_of_extended_ascii_codes
            ) * self._validation_mask
            if np.any(invalid_characters):
                bad = list(np.where(
                    invalid_characters > 0)[0].astype(np.uint8).view('|S1'))
                raise ValueError("Invalid character%s in sequence: %r" %
                                 ('s' if len(bad)>1 else '',
                                  bad if len(bad)>1 else bad[0]))

        sequence.flags.writeable = False

        self._bytes = sequence
        self._chars = sequence.view('|S1')


    def degap(self):
        """Return a new sequence with gap characters removed.

        Returns
        -------
        IUPACSequence
            A new sequence with all gap characters removed.

        See Also
        --------
        gap_chars

        Notes
        -----
        The type, id, and description of the result will be the
        same as `self`. If quality scores are present, they will be filtered in
        the same manner as the sequence and included in the resulting
        degapped sequence.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('GGUC-C--ACGTT-C.', quality=range(16))
        >>> t = s.degap()
        >>> t
        <Sequence: GGUCCACGTT... (length: 11)>
        >>> print(t)
        GGUCCACGTTC
        >>> t.quality
        array([ 0,  1,  2,  3,  5,  8,  9, 10, 11, 12, 14])

        """
        gaps = self.gap_chars
        indices = [i for i, e in enumerate(self) if e not in gaps]
        return self[indices]

    def gap_maps(self):
        """Return tuples mapping b/w gapped and ungapped positions

        Returns
        -------
        tuple containing two lists
            The first list is the length of the ungapped sequence, and each
            entry is the position of that base in the gapped sequence. The
            second list is the length of the gapped sequence, and each entry is
            either None (if that position represents a gap) or the position of
            that base in the ungapped sequence.

        See Also
        --------
        gap_vector

        Notes
        -----
        Visual aid is useful here. Imagine we have
        ``Sequence('-ACCGA-TA-')``. The position numbers in the
        ungapped sequence and gapped sequence will be as follows::

              0123456
              ACCGATA
              |||||\\
             -ACCGA-TA-
             0123456789

        So, in the first list, position 0 maps to position 1, position 1
        maps to position 2, position 5 maps to position 7, ... And, in the
        second list, position 0 doesn't map to anything (so it's None),
        position 1 maps to position 0, ...

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('-ACCGA-TA-')
        >>> m = s.gap_maps()
        >>> m[0]
        [1, 2, 3, 4, 5, 7, 8]
        >>> m[1]
        [None, 0, 1, 2, 3, 4, None, 5, 6, None]

        """
        degapped_to_gapped = []
        gapped_to_degapped = []
        non_gap_count = 0
        for i, e in enumerate(self):
            if self.is_gap(e):
                gapped_to_degapped.append(None)
            else:
                gapped_to_degapped.append(non_gap_count)
                degapped_to_gapped.append(i)
                non_gap_count += 1
        return degapped_to_gapped, gapped_to_degapped

    def gap_vector(self):
        """Return list indicating positions containing gaps

        Returns
        -------
        list of booleans
            The list will be of length ``len(self)``, and a position will
            contain ``True`` if the character at that position in the
            `Sequence` is in `self.gap_chars`, and ``False``
            otherwise.

        See Also
        --------
        gap_maps

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('..ACG--TT-')
        >>> s.gap_vector()
        [True, True, False, False, False, True, True, False, False, True]

        """
        return [self.is_gap(c) for c in self._sequence]

    @classmethod
    def is_gap(cls, char):
        """Return True if `char` is in the `gap_chars` set

        Parameters
        ----------
        char : str
            The string to check for presence in the `Sequence`
            `gap_chars`.

        Returns
        -------
        bool
            Indicates whether `char` is in the `Sequence` attribute
            `gap_chars`.

        Notes
        -----
        This is a class method.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> Sequence.is_gap('.')
        True
        >>> Sequence.is_gap('P')
        False
        >>> s = Sequence('ACACGACGTT')
        >>> s.is_gap('-')
        True

        """
        return char in cls.gap_chars

    def is_gapped(self):
        """Return True if char(s) in `gap_chars` are present

        Returns
        -------
        bool
            Indicates whether there are one or more occurences of any character
            in `self.gap_chars` in the `Sequence`.

        Examples
        --------
        >>> from skbio.sequence import Sequence
        >>> s = Sequence('ACACGACGTT')
        >>> s.is_gapped()
        False
        >>> t = Sequence('A.CAC--GACGTT')
        >>> t.is_gapped()
        True

        """
        for e in self:
            if self.is_gap(e):
                return True
        return False

    def nondegenerates(self):
        """Yield all nondegenerate versions of the sequence.

        Returns
        -------
        generator
            Generator yielding all possible nondegenerate versions of the
            sequence. Each sequence will have the same type, id, description,
            and quality scores as `self`.

        Raises
        ------
        SequenceError
            If the sequence contains an invalid character (a character that
            isn't an IUPAC character or a gap character).

        See Also
        --------
        degenerate_map

        Notes
        -----
        There is no guaranteed ordering to the generated sequences.

        Examples
        --------
        >>> from skbio.sequence import NucleotideSequence
        >>> seq = NucleotideSequence('TRG')
        >>> seq_generator = seq.nondegenerates()
        >>> for s in sorted(seq_generator, key=str): print(s)
        TAG
        TGG

        """
        degen_chars = self.degenerate_map
        nonexpansion_chars = self.nondegenerate_chars.union(
            self.gap_chars)

        expansions = []
        for char in self:
            if char in nonexpansion_chars:
                expansions.append(char)
            else:
                # Use a try/except instead of explicitly checking for set
                # membership on the assumption that an exception is rarely
                # thrown.
                try:
                    expansions.append(degen_chars[char])
                except KeyError:
                    raise SequenceError(
                        "Sequence contains an invalid character: %s" % char)

        result = product(*expansions)
        return (self.copy(sequence=nondegen_seq) for nondegen_seq in result)


class NucleotideSequence(with_metaclass(ABCMeta, IUPACSequence)):
    """Base class for nucleotide sequences.

    A `NucleotideSequence` is a `Sequence` with additional methods
    that are only applicable for nucleotide sequences, and containing only
    characters used in the IUPAC DNA or RNA lexicon.

    See Also
    --------
    Sequence

    Notes
    -----
    All uppercase and lowercase IUPAC DNA/RNA characters are supported.

    """

    @abstractmethod
    @classproperty
    def complement_map(cls):
        """Return the mapping of characters to their complements.

        Returns
        -------
        dict
            Mapping of characters to their complements.

        Notes
        -----
        Complements cannot be defined for a generic `NucleotideSequence`
        because the complement of 'A' is ambiguous.
        `NucleotideSequence.complement_map` will therefore be the empty dict.
        Thanks, nature...

        """
        pass

    @abstractmethod
    @classproperty
    def nondegenerate_chars(cls):
        """Return the non-degenerate IUPAC nucleotide characters.

        Returns
        -------
        set
            Non-degenerate IUPAC nucleotide characters.

        """
        pass

    @abstractmethod
    @classproperty
    def degenerate_map(cls):
        """Return the mapping of degenerate to non-degenerate characters.

        Returns
        -------
        dict of sets
            Mapping of IUPAC degenerate nucleotide character to the set of
            non-degenerate IUPAC nucleotide characters it represents.

        """
        pass

    def _complement(self, reverse=False):
        """Returns `NucleotideSequence` that is (reverse) complement of `self`.

        Parameters
        ----------
        reverse : bool, optional
            If ``True``, reverse `self` before complementing.

        Returns
        -------
        NucelotideSequence
            The (reverse) complement of `self`. Specific type will be the same
            as ``type(self)``.

        Raises
        ------
        skbio.sequence.SequenceError
            If a character is present in the `NucleotideSequence` that is not
            in the complement map.

        Notes
        -----
        This private method centralizes the logic for `complement` and
        `reverse_complement`.

        """
        result = []
        complement_map = self.complement_map
        seq_iterator = reversed(self) if reverse else self
        for base in seq_iterator:
            try:
                result.append(complement_map[base])
            except KeyError:
                raise SequenceError(
                    "Don't know how to complement base %s. Is it in "
                    "%s.complement_map?" % (base, self.__class__.__name__))

        quality = self.quality
        if self.has_quality() and reverse:
            quality = self.quality[::-1]

        return self.copy(sequence=result, quality=quality)

    def complement(self):
        """Return the complement of the `NucleotideSequence`

        Returns
        -------
        NucelotideSequence
            The complement of `self`. Specific type will be the same as
            ``type(self)``.

        Raises
        ------
        skbio.sequence.SequenceError
            If a character is present in the `NucleotideSequence` that is not
            in `self.complement_map`.

        See Also
        --------
        reverse_complement
        complement_map

        Notes
        -----
        The type, id, description, and quality scores of the result will be the
        same as `self`.

        """
        return self._complement()

    def is_reverse_complement(self, other):
        """Return True if `other` is the reverse complement of `self`

        Returns
        -------
        bool
            `True` if `other` is the reverse complement of `self` and `False`
            otherwise.

        Raises
        ------
        skbio.sequence.SequenceError
            If a character is present in `other` that is not in the
            `self.complement_map`.

        See Also
        --------
        reverse_complement

        """
        return self == other.reverse_complement()

    def reverse_complement(self):
        """Return the reverse complement of the `NucleotideSequence`

        Returns
        -------
        NucelotideSequence
            The reverse complement of `self`. Specific type will be the same as
            ``type(self)``.

        Raises
        ------
        skbio.sequence.SequenceError
            If a character is present in the `NucleotideSequence` that is not
            in `self.complement_map`.

        See Also
        --------
        complement
        complement_map
        is_reverse_complement

        Notes
        -----
        The type, id, and description of the result will be the same as `self`.
        If quality scores are present, they will be reversed and included in
        the resulting biological sequence.

        """
        return self._complement(reverse=True)
    rc = reverse_complement

    def find_features(self, feature_type, min_length=1, allow_gaps=False):
        """Search the sequence for features

        Parameters
        ----------
        feature_type : {'purine_run', 'pyrimidine_run'}
            The type of feature to find
        min_length : int, optional
            Defaults to 1. Only features at least as long as this will be
            returned
        allow_gaps : bool, optional
            Defaults to ``False``. If ``True``, then gaps will not be
            considered to disrupt a feature

        Returns
        -------
        generator
            Yields tuples of the start of the feature, the end of the feature,
            and the subsequence that composes the feature

        Examples
        --------
        >>> from skbio.sequence import NucleotideSequence
        >>> s = NucleotideSequence('G-AT.T')
        >>> list(s.find_features('purine_run'))
        [(0, 1, 'G'), (2, 3, 'A')]
        >>> list(s.find_features('purine_run', 2))
        []
        >>> list(s.find_features('purine_run', 2, allow_gaps=True))
        [(0, 3, 'G-A')]
        >>> list(s.find_features('pyrimidine_run', 2, allow_gaps=True))
        [(3, 6, 'T.T')]

        """
        gaps = re.escape(''.join(self.gap_chars))
        acceptable = gaps if allow_gaps else ''

        if feature_type == 'purine_run':
            pat_str = '([AGag%s]{%d,})' % (acceptable, min_length)
        elif feature_type == 'pyrimidine_run':
            pat_str = '([CTUctu%s]{%d,})' % (acceptable, min_length)
        else:
            raise ValueError("Unknown feature type: %s" % feature_type)

        pat = re.compile(pat_str)

        for hits in self.regex_iter(pat):
            if allow_gaps:
                degapped = hits[2]
                for gap_char in self.gap_chars:
                    degapped = degapped.replace(gap_char, '')
                if len(degapped) >= min_length:
                    yield hits
            else:
                yield hits


class Protein(IUPACSequence):
    """Base class for protein sequences.

    A `Protein` is a `Sequence` containing only characters
    used in the IUPAC protein lexicon.

    See Also
    --------
    Sequence

    Notes
    -----
    All uppercase and lowercase IUPAC protein characters are supported.

    """

    @classproperty
    def nondegenerate_chars(cls):
        """Return the non-degenerate IUPAC protein characters.

        Returns
        -------
        set
            Non-degenerate IUPAC protein characters.

        """
        return set("ACDEFGHIKLMNPQRSTVWY")

    @classproperty
    def degenerate_map(cls):
        """Return the mapping of degenerate to non-degenerate characters.

        Returns
        -------
        dict of sets
            Mapping of IUPAC degenerate protein character to the set of
            non-degenerate IUPAC protein characters it represents.

        """
        return {
            "B": set("DN"), "Z": set("EQ"),
            "X": set("ACDEFGHIKLMNPQRSTVWY")
        }


class DNA(NucleotideSequence):
    """Base class for DNA sequences.

    A `DNA` is a `NucelotideSequence` that is restricted to only
    containing characters used in IUPAC DNA lexicon.

    See Also
    --------
    NucleotideSequence
    Sequence

    Notes
    -----
    All uppercase and lowercase IUPAC DNA characters are supported.

    """

    @classproperty
    def complement_map(cls):
        """Return the mapping of characters to their complements.

        The complement of a gap character is itself.

        Returns
        -------
        dict
            Mapping of characters to their complements.

        """
        comp_map = {
            'A': 'T', 'T': 'A', 'G': 'C', 'C': 'G', 'Y': 'R', 'R': 'Y',
            'S': 'S', 'W': 'W', 'K': 'M', 'M': 'K', 'B': 'V', 'D': 'H',
            'H': 'D', 'V': 'B', 'N': 'N'
        }

        comp_map.update({c: c for c in cls.gap_chars})
        return comp_map

    @classproperty
    def nondegenerate_chars(cls):
        """Return the non-degenerate IUPAC DNA characters.

        Returns
        -------
        set
            Non-degenerate IUPAC DNA characters.

        """
        return set("ACGT")

    @classproperty
    def degenerate_map(cls):
        """Return the mapping of degenerate to non-degenerate characters.

        Returns
        -------
        dict of sets
            Mapping of IUPAC degenerate DNA character to the set of
            non-degenerate IUPAC DNA characters it represents.

        """
        return {
            "R": set("AG"), "Y": set("CT"), "M": set("AC"), "K": set("TG"),
            "W": set("AT"), "S": set("GC"), "B": set("CGT"), "D": set("AGT"),
            "H": set("ACT"), "V": set("ACG"), "N": set("ACGT")
        }


class RNA(NucleotideSequence):
    """Base class for RNA sequences.

    An `RNA` is a `NucelotideSequence` that is restricted to only
    containing characters used in the IUPAC RNA lexicon.

    Notes
    -----
    All uppercase and lowercase IUPAC RNA characters are supported.

    """

    @classproperty
    def complement_map(cls):
        """Return the mapping of characters to their complements.

        The complement of a gap character is itself.

        Returns
        -------
        dict
            Mapping of characters to their complements.

        """
        comp_map = {
            'A': 'U', 'U': 'A', 'G': 'C', 'C': 'G', 'Y': 'R', 'R': 'Y',
            'S': 'S', 'W': 'W', 'K': 'M', 'M': 'K', 'B': 'V', 'D': 'H',
            'H': 'D', 'V': 'B', 'N': 'N'
        }

        comp_map.update({c: c for c in cls.gap_chars})
        return comp_map

    @classproperty
    def nondegenerate_chars(cls):
        """Return the non-degenerate IUPAC RNA characters.

        Returns
        -------
        set
            Non-degenerate IUPAC RNA characters.

        """
        return set("ACGU")

    @classproperty
    def degenerate_map(cls):
        """Return the mapping of degenerate to non-degenerate characters.

        Returns
        -------
        dict of sets
            Mapping of IUPAC degenerate RNA character to the set of
            non-degenerate IUPAC RNA characters it represents.

        """
        return {
            "R": set("AG"), "Y": set("CU"), "M": set("AC"), "K": set("UG"),
            "W": set("AU"), "S": set("GC"), "B": set("CGU"), "D": set("AGU"),
            "H": set("ACU"), "V": set("ACG"), "N": set("ACGU")
        }
