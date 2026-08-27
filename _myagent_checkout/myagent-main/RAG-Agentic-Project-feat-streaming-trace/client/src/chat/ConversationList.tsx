import { useState } from "react";
import AddIcon from "@mui/icons-material/Add";
import CheckIcon from "@mui/icons-material/Check";
import CloseIcon from "@mui/icons-material/Close";
import EditOutlinedIcon from "@mui/icons-material/EditOutlined";
import DeleteOutlineIcon from "@mui/icons-material/DeleteOutline";
import SearchIcon from "@mui/icons-material/Search";
import {
  Button,
  List,
  ListItemButton,
  ListItemText,
  IconButton,
  Box,
  TextField,
  InputAdornment,
  Typography,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogContentText,
  DialogActions,
} from "@mui/material";
import type { Conversation } from "../types";

interface Props {
  conversations: Conversation[];
  selectedId: number | null;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onSelect: (id: number) => void;
  onDelete: (id: number, e: React.MouseEvent) => void;
  onRename: (id: number, newTitle: string) => void;
  onNew: () => void;
}

export default function ConversationList({
  conversations,
  selectedId,
  searchQuery,
  onSearchChange,
  onSelect,
  onDelete,
  onRename,
  onNew,
}: Props) {
  const [confirmId, setConfirmId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editTitle, setEditTitle] = useState("");

  const handleOpenConfirm = (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmId(id);
  };

  const handleConfirmDelete = (e: React.MouseEvent) => {
    if (confirmId !== null) {
      onDelete(confirmId, e);
      setConfirmId(null);
    }
  };

  const handleCloseDialog = () => {
    setConfirmId(null);
  };

  const startEditing = (c: Conversation, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingId(c.id);
    setEditTitle(c.title);
  };

  const cancelEditing = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setEditingId(null);
    setEditTitle("");
  };

  const saveEditing = (id: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    const trimmed = editTitle.trim();
    if (trimmed) {
      onRename(id, trimmed);
    }
    setEditingId(null);
    setEditTitle("");
  };

  return (
    <Box sx={{ p: 1 }}>
      <Button startIcon={<AddIcon />} fullWidth variant="outlined" onClick={onNew}>
        New conversation
      </Button>
      <TextField
        size="small"
        fullWidth
        placeholder="Search titles & messages…"
        value={searchQuery}
        onChange={(e) => onSearchChange(e.target.value)}
        sx={{ mt: 1, mb: 0.5 }}
        InputProps={{
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" color="action" />
            </InputAdornment>
          ),
          endAdornment: searchQuery ? (
            <InputAdornment position="end">
              <IconButton size="small" onClick={() => onSearchChange("")} aria-label="clear search">
                <CloseIcon fontSize="small" />
              </IconButton>
            </InputAdornment>
          ) : null,
        }}
      />
      <List dense>
        {conversations.map((c) => {
          const isEditing = editingId === c.id;
          return (
            <ListItemButton
              key={c.id}
              selected={c.id === selectedId}
              onClick={() => onSelect(c.id)}
              sx={{ pr: isEditing ? 1 : 8, position: "relative" }}
            >
              {isEditing ? (
                <Box
                  sx={{ display: "flex", alignItems: "center", width: "100%", gap: 0.5 }}
                  onClick={(e) => e.stopPropagation()}
                >
                  <TextField
                    fullWidth
                    size="small"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") saveEditing(c.id);
                      if (e.key === "Escape") cancelEditing();
                    }}
                    autoFocus
                    variant="outlined"
                    sx={{ flex: 1, minWidth: 0, "& .MuiInputBase-input": { py: 0.5, px: 1, fontSize: "0.875rem" } }}
                  />
                  <IconButton size="small" color="primary" onClick={(e) => saveEditing(c.id, e)}>
                    <CheckIcon fontSize="small" />
                  </IconButton>
                  <IconButton size="small" onClick={cancelEditing}>
                    <CloseIcon fontSize="small" />
                  </IconButton>
                </Box>
              ) : (
                <>
                  <ListItemText
                    primary={c.title}
                    sx={{ overflow: "hidden", textOverflow: "ellipsis" }}
                  />
                  <Box
                    sx={{
                      position: "absolute",
                      right: 4,
                      display: "flex",
                      alignItems: "center",
                      opacity: c.id === selectedId ? 1 : 0.4,
                      "&:hover": { opacity: 1 },
                    }}
                  >
                    <IconButton
                      size="small"
                      aria-label="rename conversation"
                      onClick={(e) => startEditing(c, e)}
                    >
                      <EditOutlinedIcon fontSize="small" />
                    </IconButton>
                    <IconButton
                      size="small"
                      aria-label="delete conversation"
                      onClick={(e) => handleOpenConfirm(c.id, e)}
                      sx={{ "&:hover": { color: "error.main" } }}
                    >
                      <DeleteOutlineIcon fontSize="small" />
                    </IconButton>
                  </Box>
                </>
              )}
            </ListItemButton>
          );
        })}
        {conversations.length === 0 && (
          <Typography
            variant="caption"
            color="text.secondary"
            sx={{ p: 2, display: "block", textAlign: "center" }}
          >
            {searchQuery ? "No matching conversations" : "No conversations yet"}
          </Typography>
        )}
      </List>

      <Dialog open={confirmId !== null} onClose={handleCloseDialog}>
        <DialogTitle>Delete Conversation?</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Are you sure you want to delete this conversation? All message and step history for this run will be permanently removed.
          </DialogContentText>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button color="error" variant="contained" onClick={handleConfirmDelete} autoFocus>
            Delete
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
