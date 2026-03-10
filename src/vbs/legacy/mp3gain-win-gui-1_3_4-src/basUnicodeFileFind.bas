Attribute VB_Name = "basUnicodeFileFind"
Option Explicit

Private Type FILETIME
        dwLowDateTime As Long
        dwHighDateTime As Long
End Type
Private Type WIN32_FIND_DATA
        dwFileAttributes As Long
        ftCreationTime As FILETIME
        ftLastAccessTime As FILETIME
        ftLastWriteTime As FILETIME
        nFileSizeHigh As Long
        nFileSizeLow As Long
        dwReserved0 As Long
        dwReserved1 As Long
        cFileName(0 To 52002) As Byte
        cAlternate(0 To 30) As Byte
End Type
Private Declare Function FindFirstFileW Lib "kernel32" (ByVal lpFileName As Long, lpFindFileData As WIN32_FIND_DATA) As Long
Private Declare Function FindNextFileW Lib "kernel32" (ByVal hFindFile As Long, lpFindFileData As WIN32_FIND_DATA) As Long
Private Declare Function FindClose Lib "kernel32" (ByVal hFindFile As Long) As Long

Private lngFlags As Long
Private findData As WIN32_FIND_DATA
Private blnFinding As Boolean
Private lngFindHandle As Long
Private strFileName As String
Private strAlternateName As String
Private Const INVALID_HANDLE_VALUE = -1

Public Function SetupUnicodeFind()
    'ReDim findData.cFileName(0 To 52002) As Byte
    'ReDim findData.cAlternate(0 To 30) As Byte
    strFileName = String$(26001, vbNullChar)
    strAlternateName = String$(15, vbNullChar)
    blnFinding = False
    lngFindHandle = 0
End Function

Public Function TrimSingleNull(ByVal strItem As String) As String
Dim intPos As Integer
    intPos = InStr(strItem, vbNullChar)
    If intPos > 0 Then
        TrimSingleNull = Left$(strItem, intPos - 1)
    Else
        TrimSingleNull = strItem
    End If
End Function

Public Function UnicodeStartFind(strFile As String, lngFlagsIn As Long, ByRef faAttributes As Long) As String
    Dim strScanFile As String
    
    If blnFinding Then
        Call FindClose(lngFindHandle)
        lngFindHandle = 0
        blnFinding = False
    End If
    
    lngFlags = lngFlagsIn
    
    strScanFile = strFile
    
    If Right$(strFile, 1) = "\" Then strScanFile = strFile & "*"
    
    lngFindHandle = FindFirstFileW(StrPtr(strScanFile), findData)
    If lngFindHandle <> INVALID_HANDLE_VALUE Then
        blnFinding = True
        If (findData.dwFileAttributes And lngFlags) <> 0 Then
            faAttributes = findData.dwFileAttributes
            CopyMemory ByVal StrPtr(strFileName), findData.cFileName(0), 52002
            UnicodeStartFind = TrimSingleNull(strFileName)
        Else
            UnicodeStartFind = UnicodeNextFind(faAttributes)
        End If
    Else
        UnicodeStartFind = ""
    End If
End Function

Public Function UnicodeNextFind(ByRef faAttributes As Long) As String
    Dim lngFindResult As Long
    Dim strOut As String
    
    If Not blnFinding Then
        UnicodeNextFind = ""
        Exit Function
    End If
    
    Do
        lngFindResult = FindNextFileW(lngFindHandle, findData)
    Loop While (lngFindResult <> 0 And ((findData.dwFileAttributes And lngFlags) = 0))
    If lngFindResult = 0 Then
        Call FindClose(lngFindHandle)
        lngFindHandle = 0
        blnFinding = False
        UnicodeNextFind = ""
        Exit Function
    End If
    
    faAttributes = findData.dwFileAttributes
    CopyMemory ByVal StrPtr(strFileName), findData.cFileName(0), 52002
    UnicodeNextFind = TrimSingleNull(strFileName)
    
End Function
