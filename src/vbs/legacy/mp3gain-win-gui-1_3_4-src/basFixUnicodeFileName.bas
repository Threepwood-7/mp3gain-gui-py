Attribute VB_Name = "basFixUnicodeFileName"
Option Explicit

Public Declare Function GetShortPathNameW Lib "kernel32" _
  (ByVal lpLongPath As Long, ByVal lpShortPath As Long, ByVal BUFSIZE As Long) As Long

Public Declare Function GetLongPathNameW Lib "kernel32" ( _
    ByVal lpszShortPath As Long, ByVal lpszLongPath As Long, ByVal cchBuffer As Long) As Long

Public Declare Function MoveFileW Lib "kernel32" ( _
    ByVal lpExistingFileName As Long, ByVal lpNewFileName As Long) As Long

Public Sub CheckFileNameOkay(strOrigShortPath As String, strOrigLongPath As String)
    Dim checkPathLong As String
    Dim lngPathLength As Long
    Dim lngRetVal As Long
    
    lngRetVal = 26000
    
    Do
        lngPathLength = lngRetVal
        checkPathLong = String$(lngPathLength + 1, 0)
        lngRetVal = GetLongPathNameW(StrPtr(strOrigShortPath), StrPtr(checkPathLong), lngPathLength)
    Loop While lngRetVal > lngPathLength
    
    If lngRetVal <= 0 Then
        Exit Sub
    End If
    
    checkPathLong = Left$(checkPathLong, lngRetVal)
    
    If checkPathLong <> strOrigLongPath Then
        'Processing accidentally truncated name. Fix it.
        Call MoveFileW(StrPtr(checkPathLong), StrPtr(strOrigLongPath))
    End If
End Sub
